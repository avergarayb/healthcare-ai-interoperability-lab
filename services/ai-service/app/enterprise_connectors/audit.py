"""Independent in-memory evidence, deliberately not durable production audit."""
from threading import RLock
from typing import Protocol

from .models import ConnectorAuditEvent, ConnectorFailure, Phase, Reason


class AuditSink(Protocol):
    def append(self, event: ConnectorAuditEvent) -> None: ...


class InMemoryAudit:
    def __init__(self):
        self._lock = RLock()
        self._events: list[ConnectorAuditEvent] = []
        self.fail_phases: set[Phase] = set()
        self.attempts = 0

    @property
    def events(self) -> tuple[ConnectorAuditEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def append(self, event: ConnectorAuditEvent) -> None:
        with self._lock:
            self.attempts += 1
            if event.phase in self.fail_phases:
                raise ConnectorFailure(Reason.AUDIT, unavailable=True)
            self._events.append(event)
