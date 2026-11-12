"""Closed provider failures. The reason code is the only public text."""


class ProviderError(Exception):
    def __init__(self, reason):
        if type(reason) is not str or reason == "":
            reason = "remote_unavailable"
        self.reason = reason
        super().__init__(reason)

    def __repr__(self):
        return "ProviderError(closed)"
