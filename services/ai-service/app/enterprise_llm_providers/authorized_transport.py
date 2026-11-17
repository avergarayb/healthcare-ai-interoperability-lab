"""One OpenAI send. The public OpenAISDKTransport.send stays blocked."""
from .errors import ProviderError
from .transport import (
    OFFICIAL_HOST, DispatchGrant, _host, dispatch_authorized, open_authorized_client,
)


class SendRelease:
    """Spent by the first send. A second send cannot borrow it."""

    def __init__(self, counter):
        self._counter = counter
        self._spent = False

    def spend(self):
        if self._spent is True:
            return False
        self._spent = True
        self._counter[0] = 1
        return True


class OneShotOpenAITransport:
    """Official Responses client. Construction does not call the API."""

    def __init__(self, credential, release, http_client=None, timeout_seconds=15):
        if type(credential) is not str or credential == "" or type(release) is not SendRelease:
            raise ProviderError("credential_absent")
        self._client = open_authorized_client(credential, timeout_seconds, http_client)
        self._release = release

    def __repr__(self):
        return "OneShotOpenAITransport(unsent)"

    def __reduce_ex__(self, protocol):
        raise TypeError("authorized transport is not portable")

    def send(self, payload, timeout_seconds):
        if self._release.spend() is not True:
            raise ProviderError("egress_blocked")
        if _host(self._client.base_url) != OFFICIAL_HOST:
            raise ProviderError("not_configured")
        if getattr(self._client.base_url, "scheme", "") != "https":
            raise ProviderError("not_configured")
        return dispatch_authorized(self._client, payload, timeout_seconds, DispatchGrant())
