"""One invocation owns the document, the grounding record and the local answer."""
from asyncio import CancelledError
import sys
from dataclasses import dataclass
from threading import Lock

from .answer import prepare_answer
from .authorization import audit_reason, final_permit, public_reason
from .delivery_sink import RecognizedDeliverySink
from .execution_types import ExecutionError
from .grounding import GroundingRecord
from .orchestration import NODES, compile_flow, invoke_flow
from ..enterprise_connectors.models import ConnectorExecutionContext, OperationRequest
from .source_boundary import TrustedEnterpriseSourceBoundary
from .sqlite_ledger import DerivedDeliveryQuery, SQLiteExecutionLedger


@dataclass(frozen=True, slots=True, repr=False)
class LocalDelivery:
    """Metadata of one attempt. The sentence stays in the recognized sink."""

    phase: str
    reason: str
    organization_id: str
    operation_id: str
    entries: int
    reservation: str
    decision: str
    observed: bool

    def __repr__(self):
        return "LocalDelivery(in-process)"

    def __reduce_ex__(self, protocol):
        raise TypeError("Local delivery is not portable")


def _denial(reason):
    mapped = {"processing_not_granted": "derived_delivery_not_granted", "profile_denied": "internal_failure"}.get(reason, reason)
    return audit_reason(mapped)


class EnterpriseAnswerFlow:
    """Read, admit and run once, then authorize and hand the sentence to one recipient."""

    def __init__(self):
        raise ExecutionError("invalid_input", unavailable=False)

    @classmethod
    def compose(cls, service, *, ledger, executor, query):
        if type(query) is not DerivedDeliveryQuery or type(ledger) is not SQLiteExecutionLedger:
            raise ExecutionError("invalid_input", unavailable=False)
        if query.organization_id != executor.organization_id:
            raise ExecutionError("scope_mismatch", unavailable=False)
        boundary = TrustedEnterpriseSourceBoundary.compose(service, ledger=ledger, executor=executor)
        flow = object.__new__(cls)
        flow._boundary = boundary
        flow._ledger = ledger
        flow._executor = executor
        flow._query = query
        flow._sink = RecognizedDeliverySink(query.recipient_id)
        flow._lock = Lock()
        flow._busy = False
        flow._started = False
        flow._answer = None
        flow._kind = None
        flow._verdict = None
        flow._days = None
        flow._months = None
        flow._record_id = None
        flow._decision = "NONE"
        flow._durable_unknown = False
        flow._spent = False
        flow._state = {}
        flow.before_authorize = None
        flow.sink_fault = None
        flow.projection = {}
        flow._compiled = compile_flow({
            "read_recognized_source": flow._read,
            "admit_gate_c": flow._admit,
            "execute_and_ground": flow._ground,
            "authorize_final": flow._authorize,
            "prepare_answer": flow._prepare,
            "deliver_local": flow._deliver,
            "finish": flow._finish,
        })
        return flow

    def __repr__(self):
        return "EnterpriseAnswerFlow(in-process)"

    def run(self, context, request):
        with self._lock:
            if self._busy or self._started:
                raise ExecutionError("lease_invalid", unavailable=False)
            self._busy = True
            self._started = True
        self._caller_context = context
        self._caller_request = request
        self._state = {
            "phase": "READING", "reason": "accepted", "organization_id": self._executor.organization_id,
            "operation_id": "", "entries": 0, "reservation": "", "decision": "NONE",
        }
        pending = False
        try:
            self.projection = dict(invoke_flow(self._compiled, dict(self._state)))
            self._state = dict(self.projection)
            return self._view()
        except BaseException:
            pending = True
            raise
        finally:
            self._days = self._months = None
            if self._answer is not None:
                self._answer.clear()
                self._answer = None
            with self._lock:
                self._busy = False
            try:
                if self._boundary.state != "CLOSED":
                    self._boundary.close()
            except BaseException:
                if not pending:
                    raise

    def receive(self, context, request):
        """Recognized identity plus the bound request. A recipient string is not enough."""
        if not self._recognized_reader(context, request):
            return None
        return self._sink.release(self._sink._token)

    def close(self):
        with self._lock:
            if self._busy:
                raise ExecutionError("lease_invalid", unavailable=False)
        if self._boundary.state != "CLOSED":
            self._boundary.close()

    def _view(self):
        return LocalDelivery(
            self._state["phase"], self._state["reason"], self._state["organization_id"],
            self._state["operation_id"], self._state["entries"], self._state["reservation"],
            self._state["decision"], self._sink.observed)

    def _mark(self, phase, reason=None, **extra):
        self._state["phase"] = phase
        if reason is not None:
            self._state["reason"] = reason
        self._state.update(extra)
        return dict(self._state)

    def _guard(self, action):
        try:
            action()
        except (CancelledError, KeyboardInterrupt):
            raise
        except ExecutionError as error:
            if self._state.get("phase") == "FINAL_AUTHORIZATION" and self._decision == "NONE" and self._boundary._operation_id:
                self._suppress("internal_failure" if error.unavailable else error.reason)
            else:
                phase = "UNCERTAIN" if error.unavailable else "DENIED"
                self._mark(phase, error.reason, decision=self._decision)
        except Exception:
            self._mark("FAILED", "internal_failure", decision=self._decision)
        return dict(self._state)

    def _read(self, _state):
        def act():
            self._boundary.read(self._caller_context, self._caller_request)
            self._mark("PROCESSING", "accepted", operation_id=self._boundary._operation_id)
        return self._guard(act)

    def _admit(self, _state):
        def act():
            self._boundary.admit()
            self._mark("GROUNDING", "accepted")
        return self._guard(act)

    def _ground(self, _state):
        def act():
            result = self._boundary.run()
            record = self._boundary._grounding
            if type(record) is GroundingRecord:
                self._record_id = id(record)
                self._verdict = record.verdict
                self._days = record.days
                self._months = record.months
            self._mark("FINAL_AUTHORIZATION", result.reason, entries=result.entries,
                       reservation=result.reservation, operation_id=result.operation_id)
            if result.state != "COMPLETED" or not self._same_record():
                self._suppress("lease_invalid" if result.state != "COMPLETED" else "internal_failure")
        return self._guard(act)

    def _authorize(self, _state):
        def act():
            if self.before_authorize is not None:
                self.before_authorize()
            with self._boundary._service.store.delivery_guard():
                if not self._same_record():
                    permit, reason = False, "lease_invalid"
                else:
                    permit, reason = final_permit(self._boundary, self._ledger, self._executor)
            try:
                decided, raw = self._ledger.commit_final_delivery(
                    self._executor, self._boundary._operation_id, self._query,
                    permit=permit, denial_reason=_denial(reason))
            except ExecutionError as error:
                self._after_commit_fault(error)
                return
            self._decision = decided
            if decided != "AUTHORIZED":
                self._mark("DENIED", public_reason(raw), decision="SUPPRESSED")
                return
            self._mark("DELIVERY", "accepted", decision="AUTHORIZED")
        return self._guard(act)

    def _prepare(self, _state):
        def act():
            if self._decision != "AUTHORIZED" or not self._same_record():
                self._mark("DENIED", "lease_invalid", decision=self._decision)
                return
            self._answer = prepare_answer(
                self._verdict, self._days, self._months, self._query.recipient_id, self._boundary._operation_id)
            self._kind = self._answer.kind
            self._mark("DELIVERY", "accepted", decision="AUTHORIZED")
        return self._guard(act)

    def _deliver(self, _state):
        def act():
            if self._answer is None or self._decision != "AUTHORIZED":
                self._mark("DENIED", "lease_invalid", decision=self._decision)
                return
            if self._spent:
                self._mark_uncertain()
                return
            self._spent = True
            self._sink.fault = self.sink_fault
            try:
                self._sink.accept(
                    recipient_id=self._query.recipient_id, operation_id=self._boundary._operation_id,
                    decision_state="AUTHORIZED", revision=self._query.processing_revision, text=self._answer._text)
            except (CancelledError, KeyboardInterrupt):
                self._seal()
                raise
            except Exception:
                self._seal()
                self._mark_uncertain()
                return
            self._answer.clear()
            self._days = self._months = None
            self._mark("DELIVERY", "accepted", decision="AUTHORIZED")
        return self._guard(act)

    def _finish(self, _state):
        if self._state["phase"] in {"DENIED", "FAILED", "UNCERTAIN"}:
            self._days = self._months = None
            return dict(self._state)
        if self._sink.observed and self._decision == "AUTHORIZED":
            phase = "INSUFFICIENT" if self._kind == "abstention" else "COMPLETED"
            return self._mark(phase, "accepted", decision="AUTHORIZED")
        if self._decision == "RELEASE_UNCERTAIN":
            return self._mark("UNCERTAIN", "execution_unknown", decision="RELEASE_UNCERTAIN")
        return self._mark("FAILED", "internal_failure", decision=self._decision)

    def _same_record(self):
        record = self._boundary._grounding
        return (type(record) is GroundingRecord and id(record) == self._record_id
                and record.verdict == self._verdict and record.days == self._days
                and record.months == self._months and record.verdict in {"EVIDENCE_FOUND", "EVIDENCE_INSUFFICIENT"}
                and self._boundary._bound is not None and self._boundary._evidence is not None)

    def _suppress(self, reason):
        if self._boundary._operation_id is None:
            self._mark("DENIED", public_reason(reason), decision="NONE")
            return
        try:
            decided, raw = self._ledger.commit_final_delivery(
                self._executor, self._boundary._operation_id, self._query,
                permit=False, denial_reason=_denial(reason))
        except ExecutionError as error:
            self._mark("UNCERTAIN" if error.unavailable else "DENIED", error.reason, decision=self._decision)
            return
        self._decision = decided
        self._mark("DENIED", public_reason(raw), decision=decided)

    def _recognized_reader(self, context, request):
        original = getattr(self, "_caller_context", None)
        original_request = getattr(self, "_caller_request", None)
        if (original is None or original_request is None or type(context) is not ConnectorExecutionContext
                or type(request) is not OperationRequest):
            return False
        try:
            recognized = self._boundary._identity.recognizes(context) is True
        except Exception:
            return False
        now = self._boundary._clock()
        return (recognized and context.authenticated_at <= now < context.expires_at
                and context.principal_id == original.principal_id
                and context.organization_id == original.organization_id == self._executor.organization_id
                and request.recipient_id == original_request.recipient_id == self._query.recipient_id
                and request.instance_id == original_request.instance_id
                and request.resource_id == original_request.resource_id
                and request.operation is original_request.operation
                and request.purpose == original_request.purpose)

    def _mark_uncertain(self):
        decision = "NONE" if self._durable_unknown else self._decision
        self._mark("UNCERTAIN", "execution_unknown", decision=decision)

    def _seal(self):
        """Record RELEASE_UNCERTAIN only after a confirming read. A failed seal stays AUTHORIZED."""
        self._spent = True
        operation_id = self._boundary._operation_id
        if operation_id is None:
            self._durable_unknown = True
            return
        try:
            state = self._ledger.delivery_decision_state(self._executor, operation_id)
        except Exception:
            self._durable_unknown = True
            return
        if state != "AUTHORIZED":
            self._durable_unknown = state is None
            if state is not None:
                self._decision = state
            return
        try:
            self._ledger.seal_release_uncertain(self._executor, operation_id)
        except Exception:
            self._decision = "AUTHORIZED"
            self._durable_unknown = False
            return
        try:
            confirmed = self._ledger.delivery_decision_state(self._executor, operation_id)
        except Exception:
            self._decision = "AUTHORIZED"
            self._durable_unknown = True
            return
        self._durable_unknown = confirmed is None
        self._decision = confirmed if confirmed is not None else "AUTHORIZED"

    def _after_commit_fault(self, error):
        self._spent = True
        state = None
        try:
            state = self._ledger.delivery_decision_state(self._executor, self._boundary._operation_id)
        except Exception:
            self._durable_unknown = True
            state = None
        if state == "AUTHORIZED":
            self._seal()
            self._mark_uncertain()
            return
        phase = "UNCERTAIN" if error.unavailable or self._durable_unknown else "DENIED"
        decision = "NONE" if state is None else state
        self._mark(phase, "execution_unknown" if self._durable_unknown else error.reason, decision=decision)

    @staticmethod
    def nodes():
        return NODES
