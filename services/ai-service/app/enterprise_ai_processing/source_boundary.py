"""Trusted laboratory composition for one read and one C02 admission.

Object identity inside this process is not a cryptographic authority. The
admission is the claimed transition plus the ExecutionOwner bound to it.
A direct EnterpriseModelGateway.prepare does not receive that claim.
"""
from asyncio import CancelledError
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import timedelta
from threading import Lock, get_ident
from uuid import UUID, uuid4

from .execution_types import ExecutionError, ExecutionOwner, LaboratoryAccess, ProcessingLease
from .gateway import EnterpriseModelGateway
from .models import (
    AIProcessingEnvelope, AIProcessingPolicy, PROFILE_ID, QUESTION, SourceEvidence,
)
from .sqlite_ledger import SQLiteExecutionLedger
from ..enterprise_connectors.models import (
    ConnectorOperation, Gate, OperationRequest, OperationResult, Outcome, UntrustedDocument,
)
from ..enterprise_connectors.policy import PolicyEvaluator
from ..enterprise_connectors.registry import PolicySnapshot
from ..enterprise_connectors.service import ConnectorService
from ..enterprise_connectors.synthetic import SyntheticDocumentAdapter


_ADMISSION = ContextVar("trusted_enterprise_source_admission", default=None)
_TRANSITIONS = {
    "NEW": {"READING", "DENIED", "CLOSED"},
    "READING": {"SOURCE_RECOGNIZED", "DENIED", "CLOSED"},
    "SOURCE_RECOGNIZED": {"PREPARE_CLAIMED", "DENIED", "CLOSED"},
    "PREPARE_CLAIMED": {"PREPARED", "DENIED", "UNCERTAIN"},
    "PREPARED": {"CLOSED"},
    "DENIED": {"CLOSED"},
    "UNCERTAIN": {"CLOSED"},
    "CLOSED": set(),
}


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeAdmission:
    """Metadata of one admitted reservation. It is not a lease and not a receipt."""

    state: str
    organization_id: str
    operation_id: str
    lease_id: str
    reservation: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Runtime admission is not portable")


class TrustedEnterpriseSourceBoundary:
    """One authorized read, one recognized result, at most one C02 admission.

    compose wires this instance to the only gateway that may prepare it.
    read and admit do not accept evidence, results, envelopes or leases.
    The lease stays here. This increment does not execute the model.
    """

    def __init__(self):
        raise ExecutionError("invalid_input", unavailable=False)

    @classmethod
    def compose(cls, service, *, ledger, executor):
        if (type(service) is not ConnectorService or service.cache_size != 0
                or type(service.adapter) is not SyntheticDocumentAdapter
                or type(service.policy) is not PolicyEvaluator
                or type(ledger) is not SQLiteExecutionLedger
                or type(executor) is not LaboratoryAccess or executor.role != "executor"
                or ledger.authority.recognizes(executor) is not True):
            raise ExecutionError("invalid_input", unavailable=False)
        boundary = object.__new__(cls)
        boundary._service = service
        boundary._ledger = ledger
        boundary._executor = executor
        boundary._clock = service.policy.clock
        boundary._identity = service.policy.identity
        boundary._lock = Lock()
        boundary._state = "NEW"
        boundary._phase_open = False
        boundary._marker = None
        boundary._thread = None
        boundary._bound = None
        boundary._populated = False
        boundary._close_started = False
        boundary._lease = None
        boundary._outstanding = None
        boundary._on_close = None
        boundary.public_reads = 0
        boundary._context = boundary._request = boundary._result = None
        boundary._document = boundary._canonical = boundary._question = None
        boundary._evidence = boundary._envelope = None
        boundary._operation_id = boundary._organization_id = None
        boundary._connector_revision = boundary._processing_revision = None
        gateway = EnterpriseModelGateway(ledger, service.policy, boundary)
        if gateway.boundary is not boundary or gateway.ledger is not ledger:
            raise ExecutionError("invalid_input", unavailable=False)
        boundary._gateway = gateway
        return boundary

    def __repr__(self):
        return "TrustedEnterpriseSourceBoundary(in-process)"

    @property
    def state(self):
        return self._state

    @property
    def outstanding_reservation(self):
        return self._outstanding

    def read(self, context, request):
        """Public read. Returns nothing the caller can hand to prepare."""
        with self._lock:
            if self._state != "NEW" or self._phase_open:
                raise ExecutionError("source_evidence_invalid", unavailable=False)
            self._move("READING")
            self._phase_open = True
        try:
            self._preflight(context, request)
            before = len(self._service.adapter.calls)
            self.public_reads += 1
            try:
                result = self._service.execute(context, request, gate=Gate.READ)
            except (CancelledError, KeyboardInterrupt):
                self._abandon("CLOSED")
                raise
            except Exception:
                self._abandon("DENIED")
                raise ExecutionError("source_evidence_invalid", unavailable=False) from None
            if len(self._service.adapter.calls) - before != 1:
                self._abandon("DENIED")
                raise ExecutionError("source_evidence_invalid", unavailable=False)
            self._commit(context, request, result)
        finally:
            with self._lock:
                self._phase_open = False

    def admit(self):
        """Claim the only preparation and call the wired gateway.prepare once."""
        with self._lock:
            if self._state != "SOURCE_RECOGNIZED" or self._phase_open:
                raise ExecutionError("source_evidence_invalid", unavailable=False)
            if not self._still_current():
                self._move("DENIED")
                self._clear_sensitive()
                raise ExecutionError("policy_changed", unavailable=False)
            self._move("PREPARE_CLAIMED")
            self._phase_open = True
            self._marker = object()
            self._thread = get_ident()
        token = _ADMISSION.set(self._marker)
        try:
            try:
                lease = self._gateway.prepare(self._envelope, self._evidence)
            except (CancelledError, KeyboardInterrupt):
                self._finish_claim("UNCERTAIN")
                raise
            except ExecutionError as error:
                self._finish_claim("UNCERTAIN" if self._uncertain(error) else "DENIED")
                raise
            except Exception:
                self._finish_claim("UNCERTAIN")
                raise ExecutionError() from None
            if type(lease) is not ProcessingLease:
                self._finish_claim("UNCERTAIN")
                raise ExecutionError("lease_invalid", unavailable=False)
            with self._lock:
                if self._state != "PREPARE_CLAIMED":
                    raise ExecutionError("source_evidence_invalid", unavailable=False)
                self._lease = lease
                self._outstanding = "HELD"
                self._move("PREPARED")
            return RuntimeAdmission("PREPARED", self._organization_id, self._operation_id, lease.reference, "HELD")
        finally:
            _ADMISSION.reset(token)
            with self._lock:
                self._phase_open = False
                self._marker = None

    def close(self):
        """Close a known, unexecuted admission through this facade's gateway.

        PREPARED cancels that gateway's reservation as CANCELLED and RELEASED.
        UNCERTAIN is left untouched. A later execution tranche must seal before
        this close; this increment does not execute the model.
        """
        hook = self._on_close
        self._on_close = None
        hook_error = None
        try:
            if hook is not None:
                hook()
        except BaseException as error:
            hook_error = error
        self._finish_close()
        if hook_error is not None:
            raise hook_error

    def recognizes_envelope(self, envelope):
        if envelope is not self._envelope or not self._bytes_intact():
            return False
        if self._state == "PREPARED":
            return self._bound is not None
        if self._state == "PREPARE_CLAIMED":
            return self._context_active() and self._bound is not None
        return False

    def recognizes_source(self, evidence, envelope):
        if evidence is not self._evidence or envelope is not self._envelope or not self._bytes_intact():
            return False
        if self._state == "PREPARED":
            return self._bound is not None
        if self._state == "PREPARE_CLAIMED":
            return self._context_active() and self._bound is not None
        return False

    def recognizes_policy(self, connector, processing):
        try:
            current = self._service.store.snapshot()
            return (type(connector) is PolicySnapshot and type(processing) is AIProcessingPolicy
                    and connector.revision == current.revision
                    and self._processing_revision is not None
                    and processing.revision == self._processing_revision
                    and self._state in {"SOURCE_RECOGNIZED", "PREPARE_CLAIMED", "PREPARED"})
        except Exception:
            return False

    def connector_snapshot(self):
        return self._service.store.snapshot()

    def authority(self, owner):
        """Bind only the owner reached by the admit thread that holds the claim."""
        with self._lock:
            if type(owner) is not ExecutionOwner:
                raise ExecutionError("source_evidence_invalid", unavailable=False)
            if owner is self._bound and self._state in {"PREPARE_CLAIMED", "PREPARED"}:
                return self._executor
            if (self._state != "PREPARE_CLAIMED" or not self._context_active()
                    or self._bound is not None or owner.original_source is not None
                    or owner.envelope is not self._envelope or owner.evidence is not self._evidence):
                raise ExecutionError("source_evidence_invalid", unavailable=False)
            self._bound = owner
            return self._executor

    def populate(self, owner):
        if (owner is not self._bound or owner.envelope is not self._envelope
                or owner.evidence is not self._evidence or not self._bytes_intact()):
            raise ExecutionError("source_evidence_invalid", unavailable=False)
        if owner.original_source is None:
            if self._populated or self._state != "PREPARE_CLAIMED":
                raise ExecutionError("source_evidence_invalid", unavailable=False)
            owner.source_bytes = self._canonical
            owner.question_bytes = self._question
            self._populated = True
            return
        if owner.original_source != self._canonical or owner.original_question != self._question:
            raise ExecutionError("source_evidence_invalid", unavailable=False)
        owner.source_bytes = self._canonical
        owner.question_bytes = self._question

    def _context_active(self):
        """The claim token is thread-local. Copying it does not transfer the admit thread."""
        return _ADMISSION.get() is self._marker and get_ident() == self._thread

    def _finish_close(self):
        with self._lock:
            if self._phase_open:
                raise ExecutionError("lease_invalid", unavailable=False)
            if self._state == "CLOSED" or self._close_started:
                return
            self._close_started = True
            cancel = self._state == "PREPARED" and self._outstanding == "HELD"
        try:
            if cancel:
                self._gateway.close()
        except BaseException:
            with self._lock:
                self._close_started = False
            raise
        with self._lock:
            if cancel:
                self._outstanding = "RELEASED"
            self._clear_sensitive()
            self._bound = None
            self._lease = None
            self._marker = None
            self._state = "CLOSED"

    def _preflight(self, context, request):
        if (self._identity.recognizes(context) is not True or type(request) is not OperationRequest
                or request.operation is not ConnectorOperation.READ
                or context.organization_id != self._executor.organization_id):
            self._abandon("DENIED")
            raise ExecutionError("identity_invalid", unavailable=False)
        snapshot = self._service.store.snapshot()
        if type(snapshot) is not PolicySnapshot or request.policy_version != snapshot.revision:
            self._abandon("DENIED")
            raise ExecutionError("policy_changed", unavailable=False)
        try:
            self._service.policy.evaluate(snapshot, context, request, Gate.READ)
            self._service.policy.evaluate(snapshot, context, request, Gate.DELIVERY)
        except Exception:
            self._abandon("DENIED")
            raise ExecutionError("source_evidence_invalid", unavailable=False) from None

    def _commit(self, context, request, result):
        if (type(result) is not OperationResult or result.status is not Outcome.DELIVERY_ALLOWED
                or result.local_status is not Outcome.LOCAL_ALLOW
                or result.external_status is not Outcome.EXTERNAL_SUCCESS
                or result.delivery_status is not Outcome.DELIVERY_ALLOWED
                or type(result.documents) is not tuple or len(result.documents) != 1):
            self._abandon("DENIED")
            raise ExecutionError("source_evidence_invalid", unavailable=False)
        document = result.documents[0]
        if (type(document) is not UntrustedDocument or type(document.text) is not str or document.text == ""
                or document.resource_id != request.resource_id
                or document.organization_id != context.organization_id
                or document.instance_id != request.instance_id):
            self._abandon("DENIED")
            raise ExecutionError("source_evidence_invalid", unavailable=False)
        after = self._service.store.snapshot()
        try:
            read = self._service.policy.evaluate(after, context, request, Gate.READ)
            canonical = document.text.encode("utf-8")
        except UnicodeError:
            self._abandon("DENIED")
            raise ExecutionError("source_evidence_invalid", unavailable=False) from None
        except Exception:
            self._abandon("DENIED")
            raise ExecutionError("source_evidence_invalid", unavailable=False) from None
        resource, binding = read.resource, read.binding
        if (type(after) is not PolicySnapshot or after.revision != request.policy_version
                or document.version != resource.version or document.version < 1 or len(canonical) < 1
                or resource.resource_id != document.resource_id
                or type(resource.classification) is not str or resource.classification == ""
                or type(result.correlation_id) is not str):
            self._abandon("DENIED")
            raise ExecutionError("source_evidence_invalid", unavailable=False)
        try:
            if str(UUID(result.correlation_id, version=4)) != result.correlation_id:
                raise ValueError
            revision = self._ledger.policy(self._executor).revision
        except Exception:
            self._abandon("DENIED")
            raise ExecutionError("source_evidence_invalid", unavailable=False) from None
        now = self._clock()
        expires = now + timedelta(seconds=5)
        if not (now < expires <= context.expires_at):
            self._abandon("DENIED")
            raise ExecutionError("authorization_expired", unavailable=False)
        evidence = SourceEvidence(
            resource.resource_id, context.organization_id, request.instance_id, binding.tenant_id,
            resource.resource_id, document.version, document.version, resource.classification,
            "synthetic-documents-v1", len(canonical), result.correlation_id, after.revision, now)
        operation_id = str(uuid4())
        envelope = AIProcessingEnvelope(
            operation_id, context, request, binding.binding_id, binding.tenant_id, evidence.source_ref,
            document.version, document.version, after.revision, revision, PROFILE_ID, 1, now, expires, QUESTION)
        with self._lock:
            if self._state != "READING":
                raise ExecutionError("source_evidence_invalid", unavailable=False)
            self._context, self._request, self._result = context, request, result
            self._document, self._canonical = document, canonical
            self._question = QUESTION.encode("utf-8")
            self._evidence, self._envelope = evidence, envelope
            self._operation_id = operation_id
            self._organization_id = context.organization_id
            self._connector_revision = after.revision
            self._processing_revision = revision
            self._move("SOURCE_RECOGNIZED")

    def _still_current(self):
        try:
            if not self._bytes_intact():
                return False
            snapshot = self._service.store.snapshot()
            revision = self._ledger.policy(self._executor).revision
            return (type(snapshot) is PolicySnapshot and snapshot.revision == self._connector_revision
                    and revision == self._processing_revision)
        except Exception:
            return False

    def _bytes_intact(self):
        document, canonical = self._document, self._canonical
        if type(document) is not UntrustedDocument or type(canonical) is not bytes:
            return False
        try:
            return document.text.encode("utf-8") == canonical
        except UnicodeError:
            return False

    def _uncertain(self, error):
        if error.unavailable:
            return True
        owner = self._bound
        return owner is not None and owner.intent_confirmed

    def _abandon(self, target):
        with self._lock:
            if self._state == "READING":
                self._clear_sensitive()
                self._move(target)

    def _finish_claim(self, target):
        with self._lock:
            if self._state == "PREPARE_CLAIMED":
                if target == "UNCERTAIN" and self._bound is not None and self._bound.intent_confirmed:
                    self._outstanding = "HELD"
                self._move(target)

    def _move(self, target):
        if target not in _TRANSITIONS[self._state]:
            raise ExecutionError("invalid_input", unavailable=False)
        self._state = target

    def _clear_sensitive(self):
        self._context = self._request = self._result = None
        self._document = self._canonical = self._question = None
        self._evidence = self._envelope = None
        self._populated = False
