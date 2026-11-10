"""C02 opt-in coordinator. No SQL, application wiring or human delivery."""
from time import monotonic
from uuid import uuid4

from .execution_types import ExecutionError, ExecutionOwner, ExecutionResult, ProcessingLease, identifier, instant, require
from .fake_model import FakeEnterpriseModel
from .models import AIProcessingEnvelope, AIProcessingPolicy, ProcessingOutcome, SourceEvidence
from .policy import GateCPolicyEvaluator
from ..enterprise_connectors.models import ConnectorExecutionContext, RegisteredPrincipal
from ..enterprise_connectors.registry import PolicySnapshot


class EnterpriseModelGateway:
    def __init__(self, ledger, connector_policy, boundary, *, model=None, monotonic_clock=monotonic):
        self.ledger, self.boundary, self.clock = ledger, boundary, connector_policy.clock
        self._identity = connector_policy.identity
        self.model = FakeEnterpriseModel(self.clock) if model is None else model
        require(type(self.model) is FakeEnterpriseModel and self.model._entry is None, "profile_denied")
        self.model._entry = self._enter_adapter
        self.monotonic = monotonic_clock
        self.evaluator = GateCPolicyEvaluator(connector_policy, self)
        self._owners, self._projection, self._snapshot = {}, None, None

    def recognizes_envelope(self, envelope):
        return self.boundary.recognizes_envelope(envelope)

    def recognizes_source(self, source, envelope):
        return self.boundary.recognizes_source(source, envelope)

    def recognizes_policy(self, connector, processing):
        return connector is self._snapshot and processing is self._projection

    def _evaluate(self, owner):
        try:
            require(type(owner.envelope) is AIProcessingEnvelope and type(owner.evidence) is SourceEvidence)
            owner.authority = self.boundary.authority(owner)
            policy = self.ledger.policy(owner.authority)
            self._snapshot = self.boundary.connector_snapshot()
            failure = ExecutionError("processing_not_granted", unavailable=False)
            for grant in policy.grants:
                self._projection = AIProcessingPolicy(policy.revision, (grant,), policy.profiles)
                decision = self.evaluator.evaluate(self._snapshot, self._projection, owner.envelope, owner.evidence)
                if decision.outcome is ProcessingOutcome.ALLOW_PROCESSING:
                    owner.grant, owner.decision = grant, decision
                    owner.profile = next(p for p in policy.profiles if p.organization_id == owner.envelope.context.organization_id
                                         and p.profile_id == owner.envelope.profile_id)
                    return
                failure = ExecutionError(decision.reason.value, unavailable=decision.outcome is ProcessingOutcome.UNAVAILABLE)
            raise failure
        finally:
            self._projection = self._snapshot = None
            owner = None

    def _assemble(self, owner):
        try:
            self.boundary.populate(owner)
            require(type(owner.source_bytes) is bytes and type(owner.question_bytes) is bytes, "source_evidence_invalid")
            owner.original_source, owner.original_question = owner.source_bytes, owner.question_bytes
            owner.input_bytes = (b"C02-input-v1\nInstruction: extract only the synthetic vacation clause; no actions.\n"
                + b"Question:" + str(len(owner.question_bytes)).encode("ascii") + b":" + owner.question_bytes
                + b"\nSource:synthetic-documents-v1;synthetic-internal;registered="
                + str(owner.evidence.registered_version).encode("ascii") + b";content="
                + str(owner.evidence.content_revision).encode("ascii") + b";bytes="
                + str(len(owner.source_bytes)).encode("ascii") + b":" + owner.source_bytes)
            require(len(owner.source_bytes) == owner.evidence.utf8_bytes, "source_evidence_invalid")
            require(len(owner.input_bytes) <= owner.envelope.limits.max_input_bytes, "budget_exceeded")
            owner.original_input = owner.input_bytes
        finally:
            owner = None

    def _metadata(self, owner):
        try:
            e, s, g = owner.envelope, owner.evidence, owner.grant
            return dict(organization_id=e.context.organization_id, operation_id=e.operation_id, attempt_version=1,
                owner_ref=str(uuid4()), process_epoch=self.ledger.process_epoch, lease_id=str(uuid4()), decision_ref=str(uuid4()),
                principal_id=e.context.principal_id, principal_type=e.context.principal_type, instance_id=e.read_request.instance_id,
                binding_id=e.binding_id, tenant_id=e.tenant_id, resource_id=e.read_request.resource_id,
                recipient_id=e.read_request.recipient_id, source_ref=e.source_ref, read_correlation_id=s.read_correlation_id,
                registered_version=s.registered_version, content_revision=s.content_revision, connector_revision=e.connector_revision,
                processing_revision=e.processing_revision, grant_id=g.grant_id, grant_version=g.version,
                approval_ref=self.ledger.approval_ref(owner.authority, g.grant_id, g.version, e.processing_revision),
                profile_id=e.profile_id, profile_version=e.profile_version,
                destination=owner.profile.destination, classification=s.classification, read_operation=e.read_request.operation.value,
                read_purpose=e.read_request.purpose, processing_operation=e.processing_operation,
                processing_purpose=e.processing_purpose, question_id="vacation-days-v1", source_bytes=len(owner.source_bytes),
                question_bytes=len(owner.question_bytes), input_bytes=len(owner.input_bytes),
                reserved_output_bytes=e.limits.max_output_bytes, reserved_output_units=e.limits.max_output_units,
                max_seconds=e.limits.max_seconds, authorized_at_us=instant(self.clock()), expires_at_us=instant(owner.decision.expires_at))
        finally:
            e = s = g = owner = None

    def prepare(self, envelope, evidence):
        owner = ExecutionOwner()
        success = False
        failure = None
        access = subject = None
        try:
            owner.envelope, owner.evidence = envelope, evidence
            with self.ledger.barrier:
                self._evaluate(owner)
                self._assemble(owner)
                self._evaluate(owner)
                owner.metadata = self._metadata(owner)
                self.ledger.reserve(owner.authority, owner.metadata)
                owner.intent_confirmed = True
                owner.lease = ProcessingLease(owner.metadata["lease_id"])
                self._owners[id(owner.lease)] = owner
                success = True
                return owner.lease
        except ExecutionError as error:
            failure = ExecutionError(error.reason, unavailable=error.unavailable)
        except Exception:
            failure = ExecutionError()
        finally:
            if not success:
                if failure is not None:
                    access, subject = self._attribution(owner)
                self._cleanup(owner)
            envelope = evidence = owner = None
        # Raise outside the dependency handler: no raw exception context escapes.
        try:
            self.ledger.deny(failure.reason, unavailable=failure.unavailable, access=access, subject=subject)
        except Exception:
            failure = ExecutionError()
        raise failure

    def _attribution(self, owner):
        """Audit identity only, not another grant/connector authorization engine."""
        context = snapshot = principal = None
        try:
            require(type(owner.envelope) is AIProcessingEnvelope
                    and self.boundary.recognizes_envelope(owner.envelope) is True)
            context = owner.envelope.context
            require(type(context) is ConnectorExecutionContext and self._identity.recognizes(context) is True)
            for name in ("principal_id", "organization_id", "principal_type", "audience", "context_version"):
                require(type(getattr(context, name)) is str)
            identifier(context.principal_id)
            identifier(context.organization_id)
            require(context.principal_type == "workload" and context.audience == "healthcare-ai-api"
                    and context.context_version == "identity-principal-context-v1")
            require(instant(context.authenticated_at) <= instant(self.clock()) < instant(context.expires_at))
            snapshot = self.boundary.connector_snapshot()
            require(type(snapshot) is PolicySnapshot and type(snapshot.principals) is tuple)
            principals = [p for p in snapshot.principals if type(p) is RegisteredPrincipal
                          and p.principal_id == context.principal_id and p.organization_id == context.organization_id
                          and p.principal_type == "workload" and p.enabled is True]
            require(len(principals) == 1)
            principal = principals[0]
            identifier(principal.principal_id)
            identifier(principal.organization_id)
            return self.boundary.authority(owner), (principal.principal_id, principal.organization_id)
        except Exception:
            return None, None  # No raw input/org refs when recognition cannot be proved.
        finally:
            context = snapshot = principal = owner = None

    def _seal(self, owner):
        try:
            self._evaluate(owner)
            self.boundary.populate(owner)
            require(owner.source_bytes == owner.original_source and owner.question_bytes == owner.original_question,
                    "source_evidence_invalid")
            require(type(owner.input_bytes) is bytes and owner.input_bytes == owner.original_input, "source_evidence_invalid")
            require(instant(self.clock()) < owner.metadata["expires_at_us"], "authorization_expired")
        finally:
            owner = None

    def _enter_adapter(self, owner):
        try:
            require(type(owner) is ExecutionOwner and owner.lease is not None
                    and self._owners.get(id(owner.lease)) is owner and owner.consuming and owner.admission_held
                    and owner.attempt_version == 2 and owner.entries == 1, "lease_invalid")
            self._seal(owner)
            owner.attempt_version = self.ledger.observe_entry(owner.authority, owner.metadata, owner.attempt_version)
            owner.admission_held = False
            self.ledger.barrier.release()
        finally:
            owner = None

    @staticmethod
    def _usage(owner, code=None):
        return dict(input_units=owner.input_units, output_bytes=owner.output_bytes, output_units=owner.output_units,
                    elapsed_us=owner.elapsed_us, result_code=code or owner.result_code or "ERROR")

    def _finish_failure(self, owner, state, reason, *, uncertain=False, preserve_cancel=False):
        try:
            if owner.intent_confirmed:
                reservation = "UNCERTAIN" if uncertain else ("CHARGED" if owner.entries else "RELEASED")
                self.ledger.finish(owner.authority, owner.metadata, owner.attempt_version, state, reason,
                                   reservation, self._usage(owner, "UNKNOWN" if uncertain else (
                                       {"CANCELLED":"CANCELLED", "TIMED_OUT":"TIMEOUT", "INVALID":"INVALID",
                                        "REVOKED":"REVOKED", "EXPIRED":"REVOKED"}.get(state, "ERROR"))))
        except BaseException as error:
            # Secondary cleanup cannot replace an already propagating signal.
            if not preserve_cancel and not isinstance(error, Exception):
                raise
        finally:
            owner = None

    def invoke_once(self, lease):
        owner = None
        acquired = False
        cleanup_ok = True
        started = self.monotonic()
        try:
            self.ledger.barrier.acquire()
            acquired = True
            candidate = self._owners.get(id(lease)) if type(lease) is ProcessingLease else None
            if candidate is None or candidate.lease is not lease or candidate.consuming:
                access, subject = self._attribution(candidate) if candidate is not None and candidate.lease is lease else (None, None)
                self.ledger.deny("lease_invalid", access=access, subject=subject)
                return ExecutionResult("DENY", "lease_invalid")
            owner, candidate = candidate, None
            owner.consuming, owner.admission_held = True, True
            self._seal(owner)
            owner.attempt_version = self.ledger.consume(owner.authority, owner.metadata, owner.attempt_version)
            self._seal(owner)  # A commit may have consumed the remaining deadline.
            self.model.invoke(owner)
            owner.elapsed_us = max(0, int((self.monotonic() - started) * 1000000))
            require(owner.elapsed_us < owner.metadata["max_seconds"] * 1000000, "deadline_exceeded")
            with self.ledger.barrier:
                self._seal(owner)
                require(type(owner.candidate) is bytes and type(owner.result_code) is str
                        and owner.result_code in {"CANDIDATE", "NO_EVIDENCE"}, "provider_result_invalid")
                owner.output_bytes = len(owner.candidate) + len(owner.result_code.encode("ascii")) + 1
                owner.output_units = owner.output_bytes
                owner.input_units = len(owner.input_bytes)
                require(owner.output_bytes <= owner.metadata["reserved_output_bytes"]
                        and owner.output_units <= owner.metadata["reserved_output_units"], "provider_result_invalid")
                self.ledger.finish(owner.authority, owner.metadata, owner.attempt_version, "COMPLETED", "accepted",
                                   "CHARGED", self._usage(owner))
            result = ExecutionResult("COMPLETED", "accepted", owner.entries, owner.started, owner.input_units, owner.output_units)
        except ExecutionError as error:
            if owner is None:
                return ExecutionResult("UNAVAILABLE" if error.unavailable else "DENY", error.reason)
            state = "UNKNOWN" if error.unavailable else ("TIMED_OUT" if error.reason == "deadline_exceeded" else (
                "INVALID" if error.reason == "provider_result_invalid" else (
                "EXPIRED" if error.reason == "authorization_expired" else "REVOKED")))
            self._finish_failure(owner, state, error.reason, uncertain=error.unavailable)
            result = ExecutionResult("UNAVAILABLE" if error.unavailable else state, error.reason, owner.entries, owner.started)
        except Exception:
            if owner is not None:
                self._finish_failure(owner, "FAILED", "provider_unavailable", uncertain=True)
            result = ExecutionResult("UNAVAILABLE", "provider_unavailable", 0 if owner is None else owner.entries,
                                     0 if owner is None else owner.started)
        except BaseException:
            if owner is not None:
                self._finish_failure(owner, "CANCELLED", "cancelled", uncertain=bool(owner.entries), preserve_cancel=True)
            raise
        finally:
            if owner is not None:
                if owner.admission_held:
                    self.ledger.barrier.release()
                acquired = False  # The adapter released it on normal entry.
                self._owners.pop(id(lease), None)
                cleanup_ok = self._cleanup(owner)
            if acquired:
                self.ledger.barrier.release()
            owner = candidate = lease = None
        return result if cleanup_ok else ExecutionResult("UNAVAILABLE", "internal_failure", result.entries, result.processing_started)

    def _cleanup(self, owner):
        ok = True
        try:
            try:
                self.ledger.retire_runtime(owner.authority, owner.metadata)
            except BaseException:
                ok = False
            try:
                owner.clear()
            except BaseException:
                ok = False
            finally:
                # Explicit sensitive slots, not frame introspection; independent
                # fallback if a composition fault breaks the ordinary clearer.
                for name in ("envelope", "evidence", "source_bytes", "question_bytes", "input_bytes", "candidate",
                             "original_source", "original_question", "original_input", "decision", "grant", "profile", "authority", "lease"):
                    object.__setattr__(owner, name, None)
                owner.done = True
            return ok
        finally:
            owner = None

    def close(self):
        with self.ledger.barrier:
            require(not any(owner.consuming for owner in self._owners.values()), "lease_invalid")
            for owner in tuple(self._owners.values()):
                self._finish_failure(owner, "CANCELLED", "cancelled")
                self._cleanup(owner)
            self._owners.clear()
