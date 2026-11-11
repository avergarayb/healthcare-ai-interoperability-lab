"""TEST ONLY single-read issuer. Not a product port, API, lease or Gate C grant.

The receipt is in-process. Object identity plus the references kept here are the
authority. A UUID, a hash or equal fields are not. content_revision is the
resource version carried by the document from that call: it is not a remote
eTag and it does not prove the remote bytes are immutable.
"""
from asyncio import CancelledError
from datetime import timedelta
from threading import Lock
from uuid import UUID, uuid4

from app.enterprise_ai_processing.execution_types import ExecutionError
from app.enterprise_ai_processing.models import (
    AIProcessingEnvelope, AIProcessingGrant, AIProcessingPolicy, ModelProcessingProfile,
    QUESTION, SourceEvidence,
)
from app.enterprise_connectors.models import (
    ConnectorOperation, Gate, OperationRequest, OperationResult, Outcome, UntrustedDocument,
)
from app.enterprise_connectors.service import ConnectorService
from app.enterprise_connectors.registry import PolicySnapshot


class TrustedSourceReadReceipt:
    """Synthetic in-memory receipt. It cannot be serialized or rebuilt from an id."""

    __slots__ = ("_issuer", "_record")

    def __init__(self, issuer, record):
        object.__setattr__(self, "_issuer", issuer)
        object.__setattr__(self, "_record", record)

    def __setattr__(self, name, value):
        raise TypeError("Trusted source receipt is not portable")

    def __delattr__(self, name):
        raise TypeError("Trusted source receipt is not portable")

    def __reduce_ex__(self, protocol):
        raise TypeError("Trusted source receipt is not portable")

    def __copy__(self):
        raise TypeError("Trusted source receipt is not portable")

    def __deepcopy__(self, memo):
        raise TypeError("Trusted source receipt is not portable")

    def __repr__(self):
        return "TrustedSourceReadReceipt(in-process)"


class _ReadRecord:
    """Strong references for one call. Not a portable token and not a lease."""

    __slots__ = (
        "context", "request", "result", "document", "canonical", "question_bytes",
        "evidence", "envelope", "receipt", "connector_revision", "content_revision",
        "external_consumed", "prepare_open", "revoked",
    )

    def __init__(self):
        self.context = self.request = self.result = self.document = None
        self.canonical = self.question_bytes = b""
        self.evidence = self.envelope = self.receipt = None
        self.connector_revision = self.content_revision = 0
        self.external_consumed = self.prepare_open = self.revoked = False


class SyntheticSingleReadIssuer:
    """One public ConnectorService.execute, then one C01 evidence for that result.

    A. The external receipt is consumed by prepare, including a failed prepare.
    B. The internal evidence stays recognizable for C02 revalidation of that
       same operation. Consumption does not delete it.
    C. The C02 lease is created only by EnterpriseModelGateway. This issuer
       does not invoke the model and does not mint a second lease.
    """

    def __init__(self, laboratory, *, ledger=None, executor=None):
        self._service = laboratory.service
        self._adapter = laboratory.adapter
        self._store = laboratory.store
        self._identity = laboratory.identity
        self._connector_policy = laboratory.policy
        self._clock = laboratory.clock
        self._ledger = ledger
        self._executor = executor
        self.public_executions = 0
        self.adapter_reads = 0
        self.observed_gates = []
        self._after_execute = None
        self._cleanup_hook = None
        self._processing = None
        self._sealed_revision = None
        self._retained = []
        self._by_evidence = {}
        self._by_envelope = {}
        self._restore = None
        self._admission = Lock()
        self._install()

    def _install(self):
        service, adapter, issuer = self._service, self._adapter, self
        original_execute, original_read = service.execute, adapter.read

        def execute(context, request, *, gate=Gate.READ):
            issuer.public_executions += 1
            issuer.observed_gates.append(gate)
            result = original_execute(context, request, gate=gate)
            if issuer._after_execute is not None:
                issuer._after_execute()
            return result

        def read(use, cursor):
            issuer.adapter_reads += 1
            return original_read(use, cursor)

        service.execute = execute
        adapter.read = read

        def restore():
            service.execute = original_execute
            adapter.read = original_read

        self._restore = restore

    def _fail(self, reason="source_evidence_invalid"):
        raise ExecutionError(reason, unavailable=False)

    def _require_call(self, context, request):
        if (self._identity.recognizes(context) is not True or type(request) is not OperationRequest
                or request.operation is not ConnectorOperation.READ or type(self._service) is not ConnectorService
                or self._service.cache_size != 0):
            self._fail()
        before = self._store.snapshot()
        if type(before) is not PolicySnapshot or request.policy_version != before.revision:
            self._fail()
        try:
            self._connector_policy.evaluate(before, context, request, Gate.READ)
            self._connector_policy.evaluate(before, context, request, Gate.DELIVERY)
        except Exception:
            self._fail()
        return before

    def read_once(self, context, request):
        before = self._require_call(context, request)
        public_before, adapter_before = self.public_executions, self.adapter_reads
        try:
            result = self._service.execute(context, request, gate=Gate.READ)
        except (CancelledError, KeyboardInterrupt):
            raise
        except Exception:
            self._fail()
        after = self._store.snapshot()
        if (self.public_executions - public_before != 1 or self.adapter_reads - adapter_before != 1
                or type(after) is not PolicySnapshot or before.revision != after.revision
                or after.revision != request.policy_version or self.observed_gates[-1] is not Gate.READ):
            self._fail()
        return self._commit(context, request, result, after)

    def _commit(self, context, request, result, snapshot):
        if (type(result) is not OperationResult or result.status is not Outcome.DELIVERY_ALLOWED
                or result.local_status is not Outcome.LOCAL_ALLOW
                or result.external_status is not Outcome.EXTERNAL_SUCCESS
                or result.delivery_status is not Outcome.DELIVERY_ALLOWED
                or type(result.documents) is not tuple or len(result.documents) != 1):
            self._fail()
        document = result.documents[0]
        if (type(document) is not UntrustedDocument or type(document.text) is not str
                or document.text == "" or document.resource_id != request.resource_id
                or document.organization_id != context.organization_id
                or document.instance_id != request.instance_id):
            self._fail()
        try:
            read = self._connector_policy.evaluate(snapshot, context, request, Gate.READ)
            canonical = document.text.encode("utf-8")
        except UnicodeError:
            self._fail()
        except Exception:
            self._fail()
        resource, binding = read.resource, read.binding
        if (document.version != resource.version or document.version < 1 or len(canonical) < 1
                or resource.resource_id != document.resource_id
                or type(resource.classification) is not str or resource.classification == ""
                or type(result.correlation_id) is not str):
            self._fail()
        try:
            if str(UUID(result.correlation_id, version=4)) != result.correlation_id:
                self._fail()
        except ValueError:
            self._fail()
        try:
            revision = 1 if self._ledger is None else self._ledger.policy(self._executor).revision
        except Exception:
            self._fail()
        now = self._clock()
        start, end = now - timedelta(seconds=1), now + timedelta(hours=1)
        expires = now + timedelta(seconds=5)
        if not (now < expires <= context.expires_at):
            self._fail()
        profile = ModelProcessingProfile(context.organization_id, start, end, end)
        grant = AIProcessingGrant(
            "processing-grant-" + request.instance_id[-1], context.principal_id, context.organization_id,
            request.instance_id, resource.tenant_id, resource.resource_id, request.recipient_id,
            start, end, end, "not_required", read_purpose=request.purpose,
            classification=resource.classification)
        policy = AIProcessingPolicy(revision, (grant,), (profile,))
        evidence = SourceEvidence(
            resource.resource_id, context.organization_id, request.instance_id, binding.tenant_id,
            resource.resource_id, document.version, document.version, resource.classification,
            "synthetic-documents-v1", len(canonical), result.correlation_id, snapshot.revision, now)
        envelope = AIProcessingEnvelope(
            str(uuid4()), context, request, binding.binding_id, binding.tenant_id, evidence.source_ref,
            document.version, document.version, snapshot.revision, revision, profile.profile_id,
            profile.version, now, expires, QUESTION)
        record = _ReadRecord()
        record.context, record.request, record.result = context, request, result
        record.document, record.canonical = document, canonical
        record.question_bytes = QUESTION.encode("utf-8")
        record.evidence, record.envelope = evidence, envelope
        record.connector_revision = snapshot.revision
        record.content_revision = document.version
        self._processing = policy
        self._sealed_revision = snapshot.revision
        self._retained.append(record)
        self._by_evidence[id(evidence)] = record
        self._by_envelope[id(envelope)] = record
        record.receipt = TrustedSourceReadReceipt(self, record)
        return record.receipt

    def _known(self, receipt):
        if type(receipt) is not TrustedSourceReadReceipt or receipt._issuer is not self:
            self._fail()
        record = receipt._record
        if record not in self._retained or record.receipt is not receipt or record.revoked:
            self._fail()
        return record

    def open_materials(self, receipt):
        record = self._known(receipt)
        return record.envelope, record.evidence, record.result, record.document

    @property
    def processing_policy(self):
        return self._processing

    def _match(self, envelope, evidence):
        record = self._by_evidence.get(id(evidence))
        if (record is None or record.evidence is not evidence or record.envelope is not envelope
                or record.revoked or record.document is None or record.context is not envelope.context
                or record.request is not envelope.read_request or record.canonical is None):
            return None
        try:
            fresh = record.document.text.encode("utf-8")
        except Exception:
            return None
        if (fresh != record.canonical or len(fresh) != evidence.utf8_bytes
                or evidence.content_revision != record.document.version
                or evidence.content_revision != record.content_revision):
            return None
        return record

    def recognizes_envelope(self, envelope):
        try:
            record = self._by_envelope.get(id(envelope))
            return record is not None and record.envelope is envelope and not record.revoked
        except Exception:
            return False

    def recognizes_source(self, evidence, envelope):
        try:
            return self._match(envelope, evidence) is not None
        except Exception:
            return False

    def recognizes_policy(self, connector, processing):
        try:
            if (type(connector) is not PolicySnapshot or type(processing) is not AIProcessingPolicy
                    or processing is not self._processing or connector is not self._store.snapshot()):
                return False
            if connector.revision != self._sealed_revision:
                self._revoke()
                return False
            return True
        except Exception:
            return False

    def _revoke(self):
        for record in self._retained:
            record.revoked = True
            record.external_consumed = True

    def connector_snapshot(self):
        return self._store.snapshot()

    def authority(self, owner):
        if self._executor is None:
            raise ExecutionError("identity_invalid", unavailable=False)
        record = self._by_envelope.get(id(owner.envelope)) if owner is not None else None
        if record is None or record.envelope is not owner.envelope:
            raise ExecutionError("identity_invalid", unavailable=False)
        if self._match(owner.envelope, owner.evidence) is None:
            raise ExecutionError("source_evidence_invalid", unavailable=False)
        return self._executor

    def populate(self, owner):
        record = self._match(owner.envelope, owner.evidence)
        if record is None:
            raise ExecutionError("source_evidence_invalid", unavailable=False)
        if owner.original_source is None:
            if record.external_consumed and not record.prepare_open:
                raise ExecutionError("source_evidence_invalid", unavailable=False)
            owner.source_bytes = record.canonical
            owner.question_bytes = record.question_bytes
            record.external_consumed = True
            return
        if owner.original_source != record.canonical:
            raise ExecutionError("source_evidence_invalid", unavailable=False)
        owner.source_bytes = record.canonical
        owner.question_bytes = record.question_bytes

    def prepare_once(self, gateway, receipt):
        """Approved admission. The lock covers only the claim, not prepare or inference."""
        record = self._known(receipt)
        with self._admission:
            if record.external_consumed or record.prepare_open or record.revoked:
                self._fail()
            if self._store.snapshot().revision != record.connector_revision:
                self._revoke()
                self._fail()
            record.prepare_open = True
        try:
            return gateway.prepare(record.envelope, record.evidence)
        finally:
            with self._admission:
                record.prepare_open = False
                record.external_consumed = True

    def close(self):
        hook = self._cleanup_hook
        try:
            if hook is not None:
                hook()
        finally:
            for record in self._retained:
                record.canonical = b""
                record.question_bytes = b""
                record.document = None
                record.evidence = None
                record.envelope = None
                record.result = None
                record.context = None
                record.request = None
                record.receipt = None
            self._retained.clear()
            self._by_evidence.clear()
            self._by_envelope.clear()
            self._processing = None
            restore = self._restore
            self._restore = None
            if restore is not None:
                restore()
