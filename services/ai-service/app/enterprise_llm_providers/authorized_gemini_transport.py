"""One Gemini send. The public GeminiSDKTransport.send stays blocked."""
from .errors import ProviderError
from .gemini_transport import DispatchGrant, dispatch_authorized, open_authorized_client, require_official_client


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


class OneShotGeminiTransport:
    """Official generateContent client. Construction does not call the API."""

    def __init__(self, credential, release, http_client=None):
        if type(credential) is not str or credential == "" or type(release) is not SendRelease:
            raise ProviderError("credential_absent")
        self._client = open_authorized_client(credential, http_client)
        self._release = release

    def __repr__(self):
        return "OneShotGeminiTransport(unsent)"

    def __reduce_ex__(self, protocol):
        raise TypeError("authorized transport is not portable")

    def send(self, generation, timeout_seconds):
        if self._release.spend() is not True:
            raise ProviderError("egress_blocked")
        require_official_client(self._client)
        if timeout_seconds != 15:
            raise ProviderError("not_configured")
        return dispatch_authorized(self._client, generation, DispatchGrant())
