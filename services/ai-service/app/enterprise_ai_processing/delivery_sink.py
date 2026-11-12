"""Recognized in-process delivery port. Callers cannot install a substitute."""
from .execution_types import ExecutionError


class RecognizedDeliverySink:
    """One recipient, one acceptance. A second acceptance is rejected."""

    def __init__(self, recipient_id):
        if type(recipient_id) is not str or recipient_id == "":
            raise ExecutionError("invalid_input", unavailable=False)
        self._recipient_id = recipient_id
        self._operation_id = None
        self._text = None
        self._used = False
        self._token = object()
        self.observed = False
        self.fault = None

    def __repr__(self):
        return "RecognizedDeliverySink(in-process)"

    def __reduce_ex__(self, protocol):
        raise TypeError("Delivery sink is not portable")

    def accept(self, *, recipient_id, operation_id, decision_state, revision, text):
        if self._used:
            raise ExecutionError("revision_conflict", unavailable=False)
        if self.fault == "before":
            self._used = True
            raise ExecutionError("internal_failure", unavailable=True)
        self._used = True
        if (recipient_id != self._recipient_id or decision_state != "AUTHORIZED"
                or type(operation_id) is not str or type(revision) is not int
                or type(text) is not str or text == ""):
            raise ExecutionError("scope_mismatch", unavailable=False)
        self._operation_id = operation_id
        self._text = text
        if self.fault == "after":
            raise ExecutionError("internal_failure", unavailable=True)
        self.observed = True

    def release(self, token):
        """The phrase leaves only with the token held by the composing flow."""
        if token is not self._token or self._text is None:
            return None
        return self._text
