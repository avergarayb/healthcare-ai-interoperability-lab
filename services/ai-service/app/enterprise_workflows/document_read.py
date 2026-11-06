"""Explicit OFFLINE composition, not a public agent, identity issuer or HTTP API.

Only safe projections cross LangGraph channels. Authority and content live in a
private, invocation-local closure, never in Runtime.context or a result registry.
"""
from contextvars import Context
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re
from typing import Protocol, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context

from ..enterprise_connectors.models import (
    ConnectorExecutionContext, ConnectorFailure, ConnectorOperation as Op, Gate,
    OperationRequest, OperationResult, Outcome, Phase, Reason, UntrustedDocument,
)
from ..enterprise_connectors.providers.microsoft_graph.adapter import GraphReadAdapter
from ..enterprise_connectors.service import ConnectorService
from ..enterprise_connectors.sqlite_store import SQLitePolicyStore


READ_OPERATIONS = frozenset({Op.METADATA, Op.CHILDREN, Op.READ})
NODES = ("validate_request", "resolve_registered_resource", "invoke_authorized_connector", "evaluate_result")


@dataclass(frozen=True, slots=True, repr=False)
class VerifiedInvocation:
    """Internal port value. Merely constructing/copying one grants no authority."""
    context: ConnectorExecutionContext
    instance_id: str
    resource_id: str
    operation: Op
    purpose: str
    recipient_id: str
    policy_version: int
    expires_at: datetime
    modality: str = "enterprise"
    mode: str = "application"


class InvocationBoundary(Protocol):
    """Trusted composition supplies this port; the synthetic issuer is TEST ONLY.

    open verifies/authorizes a fresh, fixed request and recipient independently
    of tool arguments. recognizes rechecks its lifetime; close retires the value.
    This is not implemented by the existing workload HTTP endpoint.
    """
    def open(self) -> VerifiedInvocation: ...
    def recognizes(self, envelope: VerifiedInvocation) -> bool: ...
    def close(self, envelope: VerifiedInvocation) -> None: ...


class EnterpriseState(TypedDict, total=False):
    operation_id: str
    correlation_id: str | None
    resource_id: str | None
    operation: str | None
    status: str
    reason: str
    steps: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RunInfo:
    operation_id: str


@dataclass(frozen=True, slots=True)
class EnterpriseResult:
    operation_id: str
    correlation_id: str | None
    status: Outcome
    reason: Reason
    steps: tuple[str, ...]
    # No public lookup API exists. These values leave only this authorized call.
    documents: tuple[UntrustedDocument, ...] = field(default=(), repr=False)


@dataclass(slots=True, repr=False)
class _Invocation:
    info: RunInfo
    arguments: object
    envelope: VerifiedInvocation | None = None
    request: OperationRequest | None = None
    result: OperationResult | None = None
    interruption: BaseException | None = None
    deadline: datetime | None = None
    steps: tuple[str, ...] = ()

    def clear(self):
        """Idempotent removal, not erasure of strings or consumer-owned copies."""
        _force_clear(self)


def _force_clear(frame):
    # Exact private slots: bypass custom cleanup and still visit every field.
    try:
        object.__setattr__(frame, "result", None)
    finally:
        try:
            object.__setattr__(frame, "envelope", None)
        finally:
            try:
                object.__setattr__(frame, "request", None)
            finally:
                try:
                    object.__setattr__(frame, "arguments", None)
                finally:
                    object.__setattr__(frame, "interruption", None)


def _scrub_owned_tracebacks(error, owner):
    """Clear completed frames of this exact owner, not just this module.

    Never traverse/clear arbitrary fixture, library, consumer or global memory.
    Exception chains may include other invocations, even of the same workflow.
    Executing owner/facade frames use their own explicit finally blocks.
    """
    if owner is None:
        return  # Construction was interrupted before an owner was available.
    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        pending.extend(item for item in (current.__cause__, current.__context__) if item is not None)
        if isinstance(current, BaseExceptionGroup):
            pending.extend(current.exceptions)
        tb = current.__traceback__
        while tb is not None:
            if (tb.tb_frame.f_globals is globals()
                    and (tb.tb_frame.f_locals.get("frame") is owner
                         or tb.tb_frame.f_locals.get("self") is owner)):
                try:
                    tb.tb_frame.clear()
                except RuntimeError:
                    pass  # A currently executing facade cannot be cleared here.
            tb = tb.tb_next


class EnterpriseDocumentWorkflow:
    """Internal capability enterprise_document_read, registered only by its owner.

    No caller-supplied identity, RunnableConfig, callbacks, thread, checkpoint,
    store, resume command, result handle or streaming interface is accepted.
    Python code holding these ports is trusted; this is not process isolation.
    """
    capability = "enterprise_document_read"

    def __init__(self, service: ConnectorService, boundary: InvocationBoundary):
        if (type(service) is not ConnectorService or type(service.store) is not SQLitePolicyStore
                or type(service.adapter) is not GraphReadAdapter or service.cache_size != 0
                or service.adapter.transport.offline is not True
                or service.adapter.credentials.offline is not True):
            raise ValueError("Explicit offline Graph/SQLite composition without content cache required")
        self._service, self._boundary = service, boundary

    def invoke(self, arguments) -> EnterpriseResult:
        # Isolate inherited LangChain configs/callbacks and LangSmith tracing.
        try:
            return Context().run(self._invoke, arguments)
        finally:
            arguments = None

    def _trusted(self, frame):
        envelope = frame.envelope
        try:
            if (type(envelope) is not VerifiedInvocation or not self._boundary.recognizes(envelope)
                    or type(envelope.context) is not ConnectorExecutionContext
                    or not self._service.policy.identity.recognizes(envelope.context)
                    or envelope.modality != "enterprise" or envelope.mode != "application"):
                raise ConnectorFailure(Reason.IDENTITY)
            now = self._service.policy.clock()
            try:
                # Context checked by the service must not outlive its envelope.
                if envelope.context.expires_at > envelope.expires_at:
                    raise ConnectorFailure(Reason.IDENTITY)
                if now >= envelope.expires_at or (frame.deadline is not None and now >= frame.deadline):
                    raise ConnectorFailure(Reason.EXPIRED)
            except (TypeError, ValueError):
                raise ConnectorFailure(Reason.IDENTITY) from None
            return envelope
        finally:
            envelope = None

    def _failure(self, frame, reason, *, unavailable=False):
        service = self._service
        previous = frame.result if type(frame.result) is OperationResult else None
        context = None
        try:
            correlation = previous.correlation_id if previous is not None else str(uuid4())
            local = previous.local_status if previous is not None else Outcome.DENY
            external = previous.external_status if previous is not None else None
            status = Outcome.UNAVAILABLE if unavailable else (
                Outcome.DENY if local == Outcome.DENY else Outcome.DELIVERY_SUPPRESSED)
            try:
                if type(frame.envelope) is VerifiedInvocation and self._boundary.recognizes(frame.envelope):
                    context = frame.envelope.context
            except Exception:
                pass  # Unverifiable boundary must not create an attributed actor.
            # Reuse closed audit vocabulary and attribution, never raw args.
            try:
                service._event(context, frame.request, correlation,
                               Phase.AUTHORIZATION if local == Outcome.DENY else Phase.DELIVERY,
                               status, reason)
            except Exception:
                status, reason = Outcome.UNAVAILABLE, Reason.AUDIT
            frame.result = OperationResult(status, reason, correlation, local, external)
        finally:
            previous = context = None

    def _projection(self, frame):
        result = frame.result
        try:
            return EnterpriseState(
                operation_id=frame.info.operation_id,
                correlation_id=None if result is None else result.correlation_id,
                resource_id=None if frame.request is None else frame.request.resource_id,
                operation=None if frame.request is None else frame.request.operation.value,
                status="pending" if result is None else result.status.value,
                reason=Reason.ALLOWED.value if result is None else result.reason.value,
                steps=frame.steps,
            )
        finally:
            result = None

    def _compile(self, frame):
        def node(name, action):
            def run(state: EnterpriseState, runtime: Runtime[RunInfo]):
                try:
                    try:
                        if frame.interruption is not None:
                            raise frame.interruption
                        if (runtime.context is not frame.info or state.get("operation_id") != frame.info.operation_id
                                or tuple(state.get("steps", ())) != frame.steps):
                            raise ConnectorFailure(Reason.REPLAY)
                        frame.steps += (name,)
                        action()
                    except ConnectorFailure as error:
                        self._failure(frame, error.reason, unavailable=error.unavailable)
                    except Exception:
                        self._failure(frame, Reason.POLICY, unavailable=True)
                    return self._projection(frame)
                except BaseException as error:
                    # Protect the action, error handlers AND projection: the
                    # runtime may wrap a cancelled task in an ordinary exception.
                    if not isinstance(error, Exception) and frame.interruption is None:
                        frame.interruption = error
                    raise
            return run

        def validate():
            frame.envelope = self._boundary.open()
            envelope = args = None
            try:
                envelope = self._trusted(frame)
                args = frame.arguments
                if (type(args) is not dict or set(args) != {"resource_id", "operation", "purpose"}
                        or any(type(value) is not str or not 1 <= len(value) <= 64 for value in args.values())
                        or not re.fullmatch(r"[A-Za-z0-9.-]{1,64}", args["resource_id"])):
                    raise ConnectorFailure(Reason.OPERATION)
                if (type(envelope.operation) is not Op or envelope.operation not in READ_OPERATIONS
                        or args["resource_id"] != envelope.resource_id or args["operation"] != envelope.operation.value
                        or args["purpose"] != envelope.purpose):
                    raise ConnectorFailure(Reason.OPERATION)
                frame.request = OperationRequest(envelope.instance_id, envelope.resource_id, envelope.operation,
                                                 envelope.purpose, envelope.recipient_id, envelope.policy_version)
            finally:
                envelope = args = None

        def resolve():
            envelope = evaluation = None
            try:
                envelope = self._trusted(frame)
                service = self._service
                # The existing evaluator, not a second policy engine, resolves grants.
                evaluation = service.policy.evaluate(service.store.snapshot(), envelope.context, frame.request)
                service.adapter.catalog.resolve(evaluation.resource, service.store.snapshot())
                frame.deadline = min(envelope.expires_at, evaluation.expires_at,
                                     service.policy.clock() + timedelta(seconds=evaluation.definition.limits.max_seconds))
            finally:
                envelope = evaluation = None

        def invoke_connector():
            envelope = result = None
            try:
                envelope = self._trusted(frame)
                result = self._service.execute(envelope.context, frame.request)
                if (type(result) is not OperationResult or type(result.status) is not Outcome
                        or type(result.reason) is not Reason):
                    raise ConnectorFailure(Reason.POLICY, unavailable=True)
                frame.result = result
            finally:
                envelope = result = None

        def evaluate():
            self._trusted(frame)
            result = frame.result
            try:
                terminal = {Outcome.DENY, Outcome.UNAVAILABLE, Outcome.EXTERNAL_DENIED,
                            Outcome.DELIVERY_SUPPRESSED, Outcome.DELIVERY_ALLOWED}
                if (type(result) is not OperationResult or type(result.status) is not Outcome
                        or result.status not in terminal or (result.status != Outcome.DELIVERY_ALLOWED and result.documents)
                        or (result.status == Outcome.DELIVERY_ALLOWED and (
                            result.local_status != Outcome.LOCAL_ALLOW or result.external_status != Outcome.EXTERNAL_SUCCESS
                            or result.delivery_status != Outcome.DELIVERY_ALLOWED))):
                    raise ConnectorFailure(Reason.POLICY, unavailable=True)
            finally:
                result = None

        graph = StateGraph(EnterpriseState, context_schema=RunInfo)
        for name, action in zip(NODES, (validate, resolve, invoke_connector, evaluate)):
            graph.add_node(name, node(name, action), retry_policy=None)
        graph.add_edge(START, NODES[0])
        for current, following in zip(NODES, NODES[1:]):
            if current == NODES[2]:
                graph.add_edge(current, following)
            else:
                graph.add_conditional_edges(current, lambda state: "end" if frame.result is not None else "next",
                                            {"end": END, "next": following})
        graph.add_edge(NODES[-1], END)
        return graph.compile(checkpointer=False, store=None, cache=None, debug=False,
                             name="offline_enterprise_document_read")

    def _deliver(self, frame):
        if frame.result.status != Outcome.DELIVERY_ALLOWED:
            return
        self._trusted(frame)
        service = self._service
        try:
            # The graph may have finished after the service's earlier B decision.
            # Revalidate and audit at the actual, non-streaming output boundary.
            with service.store.delivery_guard():
                self._trusted(frame)
                service.policy.evaluate(service.store.snapshot(), frame.envelope.context, frame.request, Gate.READ)
                service._validate_delivery(frame.envelope.context, frame.request, frame.result.documents, False)
                service._event(frame.envelope.context, frame.request, frame.result.correlation_id,
                               Phase.DELIVERY, Outcome.DELIVERY_ALLOWED, Reason.ALLOWED)
                service._validate_delivery(frame.envelope.context, frame.request, frame.result.documents, False)
                self._trusted(frame)
            # Exiting the guard commits; failed commit must not deliver content.
        except ConnectorFailure as error:
            self._failure(frame, error.reason, unavailable=error.unavailable)
        except Exception:
            self._failure(frame, Reason.POLICY, unavailable=True)

    def _run(self, frame):
        try:
            with tracing_context(enabled=False, parent=False):
                graph = self._compile(frame)
                graph.invoke(self._projection(frame), context=frame.info,
                             config={"callbacks": [], "recursion_limit": 8})
                if frame.interruption is not None:
                    raise frame.interruption
                if frame.result is None:
                    raise ConnectorFailure(Reason.POLICY, unavailable=True)
                self._deliver(frame)
        except ConnectorFailure as error:
            if frame.interruption is not None:
                raise frame.interruption
            self._failure(frame, error.reason, unavailable=error.unavailable)
        except Exception:
            if frame.interruption is not None:
                raise frame.interruption
            self._failure(frame, Reason.POLICY, unavailable=True)

    def _close(self, frame, primary):
        try:
            if frame.envelope is not None:
                self._boundary.close(frame.envelope)
        except BaseException as error:
            if primary is not None:
                # Observe cleanup failure without replacing the original signal
                # or attaching a second exception/body with sensitive references.
                BaseException.add_note(primary, "enterprise_lease_cleanup_failed")
            elif isinstance(error, Exception):
                self._failure(frame, Reason.IDENTITY, unavailable=True)
            else:
                raise

    def _invoke(self, arguments):
        frame = None
        primary = None
        try:
            try:
                # Create the owner inside the protected region, initially empty.
                frame = _Invocation(RunInfo(str(uuid4())), None)
                frame.arguments = arguments
                try:
                    self._run(frame)
                except BaseException as error:
                    primary = error
                    raise
                finally:
                    self._close(frame, primary)
                # No local alias to the sensitive intermediate result survives.
                return EnterpriseResult(frame.info.operation_id, frame.result.correlation_id,
                                        frame.result.status, frame.result.reason, frame.steps,
                                        frame.result.documents)
            except BaseException as error:
                primary = error
                raise
            finally:
                try:
                    if frame is not None:
                        frame.clear()
                except BaseException:
                    if primary is None:
                        raise
                    BaseException.add_note(primary, "enterprise_frame_cleanup_failed")
                finally:
                    # Even an interrupted/custom clear cannot bypass the exact slots.
                    if frame is not None:
                        _force_clear(frame)
                    arguments = primary = None
        except BaseException as error:
            # Cleanup has finished; only completed frames retaining this exact
            # invocation owner may now be scrubbed. Foreign chains stay intact.
            _scrub_owned_tracebacks(error, frame)
            raise
