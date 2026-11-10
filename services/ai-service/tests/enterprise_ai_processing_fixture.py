"""TEST ONLY C01 owner/configuration issuer over existing in-memory A/B ports."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from uuid import uuid4

from app.enterprise_ai_processing.models import (
    AIProcessingEnvelope, AIProcessingGrant, AIProcessingPolicy, ModelProcessingProfile,
    PROFILE_ID, QUESTION, SourceEvidence,
)
from app.enterprise_ai_processing.policy import GateCPolicyEvaluator
from app.enterprise_connectors.models import (
    ConnectorExecutionContext, Gate, OperationRequest, Outcome, QualifiedExternalResource, UntrustedDocument,
)
from tests.enterprise_connector_fixture import laboratory


@dataclass(frozen=True, slots=True, repr=False)
class SourceOwner:
    operation_id: str
    evidence: SourceEvidence
    document: UntrustedDocument
    original_text: str
    context: ConnectorExecutionContext
    request: OperationRequest
    content_revision: int
    correlation_id: str
    observed_at: datetime
    resource: QualifiedExternalResource


class SyntheticProcessingBoundary:
    """Per-fixture registry only. No HTTP, production issuer, lease or admin API."""
    def __init__(self, connector_snapshot, policy, authorize_source):
        self.connector_snapshot, self.policy = connector_snapshot, policy
        self.authorize_source = authorize_source  # Existing public in-memory permission check only.
        self.envelopes, self.sources = {}, {}

    def recognizes_envelope(self, envelope):
        return self.envelopes.get(id(envelope)) is envelope

    def recognizes_policy(self, connector, processing):
        return connector is self.connector_snapshot and processing is self.policy

    def recognizes_source(self, source, envelope):
        owner = self.sources.get(id(source))
        valid = (owner is not None and owner.evidence is source and owner.context is envelope.context
                and owner.operation_id == envelope.operation_id and owner.request is envelope.read_request
                and type(owner.document) is UntrustedDocument and owner.document.text == owner.original_text
                and owner.content_revision == source.content_revision
                and source.utf8_bytes == len(owner.original_text.encode("utf-8"))
                and source.connector_revision == owner.request.policy_version
                and source.read_correlation_id == owner.correlation_id
                and source.observed_at == owner.observed_at
                and (source.organization_id, source.instance_id, source.resource_id, source.registered_version)
                == (owner.document.organization_id, owner.document.instance_id,
                    owner.document.resource_id, owner.document.version))
        if not valid:
            return False
        self.authorize_source((owner.resource,))
        return True

    def remember(self, envelope):
        self.envelopes[id(envelope)] = envelope
        return envelope


class ProcessingLaboratory:
    def __init__(self):
        self.connector = laboratory()
        self.clock = self.connector.clock
        now, expiry = self.clock(), self.clock() + timedelta(minutes=2)
        profiles, grants = [], []
        for suffix, organization in (("a", "ORG-A"), ("b", "ORG-B")):
            profiles.append(ModelProcessingProfile(organization, now, expiry, expiry))
            grants.append(AIProcessingGrant("processing-grant-" + suffix, "principal-" + suffix,
                organization, "instance-" + suffix, "tenant-" + suffix, "vacation-" + suffix,
                "recipient-" + suffix, now, expiry, expiry, approval="not_required"))
        self.boundary = SyntheticProcessingBoundary(self.connector.store.snapshot(),
            AIProcessingPolicy(1, tuple(grants), tuple(profiles)), self.connector.adapter.authorize_delivery)
        self.evaluator = GateCPolicyEvaluator(self.connector.policy, self.boundary)
        self.envelope, self.source = self.issue()

    @property
    def policy(self):
        return self.boundary.policy

    def issue(self, suffix="a", *, resource=None, question=QUESTION, content_revision=1):
        """Read via public service once in setup, not during C01 evaluation."""
        context = self.connector.a if suffix == "a" else self.connector.b
        request = self.connector.request(suffix, resource=resource)
        result = self.connector.service.execute(context, request)
        if result.status is not Outcome.DELIVERY_ALLOWED or len(result.documents) != 1:
            raise ValueError("Fixture requires a real authorized synthetic A/B result")
        snapshot = self.connector.store.snapshot()
        read = self.connector.policy.evaluate(snapshot, context, request, Gate.READ)
        self.connector.policy.evaluate(snapshot, context, request, Gate.DELIVERY)
        document = result.documents[0]
        now = self.clock()
        source = SourceEvidence(str(uuid4()), context.organization_id, request.instance_id,
            read.binding.tenant_id, request.resource_id, document.version, content_revision,
            read.resource.classification, "synthetic-documents-v1", len(document.text.encode("utf-8")),
            result.correlation_id, snapshot.revision, now)
        envelope = AIProcessingEnvelope(str(uuid4()), context, request, read.binding.binding_id,
            read.binding.tenant_id, source.source_ref, document.version, content_revision, snapshot.revision,
            self.policy.revision, PROFILE_ID, 1, now, min(context.expires_at, now + timedelta(seconds=5)), question)
        self.boundary.sources[id(source)] = SourceOwner(envelope.operation_id, source, document, document.text,
            context, request, content_revision, result.correlation_id, now, read.resource)
        self.boundary.connector_snapshot = snapshot
        return self.boundary.remember(envelope), source

    def reissue(self, **overrides):
        """Allow malformed trusted records in negative tests; never user authority."""
        self.envelope = self.boundary.remember(replace(self.envelope, **overrides))
        return self.envelope

    def replace_source(self, **overrides):
        previous = self.source
        self.source = replace(previous, **overrides)
        self.boundary.sources[id(self.source)] = replace(self.boundary.sources[id(previous)], evidence=self.source)
        return self.source

    def configure(self, *, grants=None, profiles=None, revision=None):
        self.boundary.policy = replace(self.policy,
            grants=self.policy.grants if grants is None else grants,
            profiles=self.policy.profiles if profiles is None else profiles,
            revision=self.policy.revision + 1 if revision is None else revision)

    def refresh_connector(self):
        self.boundary.connector_snapshot = self.connector.store.snapshot()

    def evaluate(self, **overrides):
        arguments = dict(connector_snapshot=self.boundary.connector_snapshot,
                         processing_policy=self.policy, envelope=self.envelope, evidence=self.source)
        return self.evaluator.evaluate(**{**arguments, **overrides})


def processing_laboratory():
    return ProcessingLaboratory()
