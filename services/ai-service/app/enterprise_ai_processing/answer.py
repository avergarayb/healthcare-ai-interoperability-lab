"""Trusted vacation template. The caller cannot supply the sentence or the figures."""
from dataclasses import dataclass

from .execution_types import ExecutionError


QUESTION_ID = "vacation-days-v1"
ABSTENTION = "El documento consultado no establece una cláusula de vacaciones verificable."


@dataclass(slots=True, repr=False)
class EphemeralAnswer:
    """One in-process sentence. It is not a ledger row and not a graph value."""

    kind: str
    recipient_id: str
    operation_id: str
    classification: str = "synthetic-internal"
    _text: str | None = None

    def __repr__(self):
        return "EphemeralAnswer(in-process)"

    def __reduce_ex__(self, protocol):
        raise TypeError("Ephemeral answer is not portable")

    def clear(self):
        self._text = None


def _render(days, months):
    if type(days) is not int or type(months) is not int or not 0 <= days <= 999 or not 0 <= months <= 999:
        raise ExecutionError("invalid_input", unavailable=False)
    return ("Según el documento consultado, corresponden " + str(days)
            + " días de vacaciones tras " + str(months) + " meses de servicio.")


def prepare_answer(verdict, days, months, recipient_id, operation_id):
    if verdict == "EVIDENCE_FOUND":
        text = _render(days, months)
        kind = "answer"
    elif verdict == "EVIDENCE_INSUFFICIENT":
        text = ABSTENTION
        kind = "abstention"
    else:
        raise ExecutionError("source_evidence_invalid", unavailable=False)
    answer = EphemeralAnswer(kind, recipient_id, operation_id)
    answer._text = text
    return answer
