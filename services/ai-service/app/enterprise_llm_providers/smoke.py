"""One fixed synthetic dry-run. It has no document argument and cannot select the SDK transport."""
from .adapter import OpenAIResponsesAdapter
from .errors import ProviderError
from .permit import PURPOSE, CLASSIFICATION, SyntheticRead
from .schema import QUESTION_ID


FIXED_DOCUMENT = "VACACIONES: 20 dias tras 12 meses de servicio."
FIXED_ORGANIZATION = "ORG-A"
FIXED_PRINCIPAL = "principal-a"
FIXED_INSTANCE = "instance-a"
FIXED_RESOURCE = "vacation-a"


class _ScriptedTransport:
    def __init__(self, body):
        self.body = body
        self.calls = 0

    def send(self, payload, timeout_seconds):
        self.calls += 1
        return self.body


def dry_run_fixed_fixture(settings, permit, clock, scripted_body):
    if type(scripted_body) is not dict or not callable(clock):
        raise ProviderError("invalid_input")
    transport = _ScriptedTransport(scripted_body)
    reading = SyntheticRead(
        FIXED_ORGANIZATION, FIXED_PRINCIPAL, FIXED_INSTANCE, FIXED_RESOURCE,
        PURPOSE, CLASSIFICATION, QUESTION_ID, FIXED_DOCUMENT.encode("utf-8"))
    return OpenAIResponsesAdapter(settings, transport, clock).observe(reading, permit)
