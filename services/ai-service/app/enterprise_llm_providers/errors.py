"""Closed provider failures. The reason code is the only public text."""

_FINISH = frozenset({
    "FINISH_REASON_UNSPECIFIED", "STOP", "MAX_TOKENS", "SAFETY", "RECITATION", "LANGUAGE",
    "OTHER", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "MALFORMED_FUNCTION_CALL",
    "UNEXPECTED_TOOL_CALL", "absent", "unrecognized",
})
_FLAGS = (
    "candidate_present", "content_present", "usage_present", "cost_exact",
    "prompt_inferred", "visible_inferred", "thoughts_inferred", "tool_inferred",
)
_COUNTS = ("input_tokens", "candidate_tokens", "thoughts_tokens", "output_tokens")


class ProviderError(Exception):
    def __init__(self, reason, diagnostic=None):
        if type(reason) is not str or reason == "":
            reason = "remote_unavailable"
        self.reason = reason
        self.diagnostic = _diagnostic(diagnostic)
        super().__init__(reason)

    def __repr__(self):
        return "ProviderError(closed)"


def _diagnostic(diagnostic):
    """Keep finish and token counts. Drop every free-text field."""
    if type(diagnostic) is not dict:
        return None
    finish = diagnostic.get("finish_reason")
    closed = {"finish_reason": finish if finish in _FINISH else "unrecognized"}
    for name in _FLAGS:
        value = diagnostic.get(name)
        closed[name] = value if type(value) is bool else None
    for name in _COUNTS:
        value = diagnostic.get(name)
        closed[name] = value if type(value) is int and not isinstance(value, bool) and value >= 0 else None
    return closed
