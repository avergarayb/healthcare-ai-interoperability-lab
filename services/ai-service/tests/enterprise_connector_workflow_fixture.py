"""TEST ONLY verified invocation issuer and offline workflow composition."""
from dataclasses import replace
from datetime import timedelta
from threading import RLock

from app.enterprise_workflows.document_read import EnterpriseDocumentWorkflow, VerifiedInvocation
from app.enterprise_connectors.models import ConnectorExecutionContext, ConnectorOperation as Op
from tests.enterprise_connector_graph_fixture import graph_laboratory


class TestInvocationBoundary:
    __test__ = False

    def __init__(self, lab, *, suffix="a", resource=None, operation=Op.READ):
        self.lab, self.suffix = lab, suffix
        self.resource, self.operation = resource or "vacation-" + suffix, operation
        self._lock, self._issued, self._leases = RLock(), {}, {}
        self.overrides, self.context_override = {}, None
        self.transform = lambda envelope: envelope
        self.before_open, self.before_close = lambda: None, lambda: None
        self.accepted = True

    def open(self):
        self.before_open()
        p = self.lab.persistent
        context = p.identity.issue("principal-" + self.suffix, expires_at=p.clock() + timedelta(seconds=5)) \
            if self.context_override is None else self.context_override
        expiry = context.expires_at if type(context) is ConnectorExecutionContext else p.clock() + timedelta(seconds=5)
        envelope = VerifiedInvocation(context, "instance-" + self.suffix, self.resource,
            self.operation, "synthetic-demonstration", "recipient-" + self.suffix,
            p.revision, expiry)
        envelope = replace(envelope, **self.overrides)
        value = self.transform(envelope)
        with self._lock:
            self._issued[id(envelope)] = envelope
            self._leases[id(value)] = envelope
        return value

    def recognizes(self, envelope):
        with self._lock:
            return self.accepted and self._issued.get(id(envelope)) is envelope

    def close(self, envelope):
        try:
            self.before_close()
        finally:
            with self._lock:
                original = self._leases.pop(id(envelope), None)
                if original is not None:
                    self._issued.pop(id(original), None)

    def arguments(self):
        return {"resource_id": self.resource, "operation": self.operation.value,
                "purpose": "synthetic-demonstration"}


def workflow_laboratory(tmp_path, **kwargs):
    lab = graph_laboratory(tmp_path, **kwargs)
    boundary = TestInvocationBoundary(lab)
    return lab, boundary, EnterpriseDocumentWorkflow(lab.service, boundary)
