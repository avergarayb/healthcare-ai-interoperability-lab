"""Fixed offline adapter and extractive core. No storage, SQL or external hooks."""
from .execution_types import ExecutionOwner, instant, require


class FakeEnterpriseModel:
    def __init__(self, clock):
        self.clock, self._entry = clock, None

    def invoke(self, owner):
        """Actual adapter entry; the bound internal gate durably observes it."""
        try:
            require(type(owner) is ExecutionOwner and self._entry is not None, "lease_invalid")
            owner.entries += 1
            self._entry(owner)
            self._extract(owner)
        finally:
            owner = None

    def _extract(self, owner):
        """Only owner holds bytes; no Python helper receives a raw payload."""
        try:
            require(instant(self.clock()) < owner.metadata["expires_at_us"], "deadline_exceeded")
            owner.started += 1
            owner.input_units = len(owner.input_bytes)
            start = owner.source_bytes.find(b"VACACIONES: ")
            days = start + 12
            middle = owner.source_bytes.find(b" dias tras ", days) if start >= 0 else -1
            months = middle + 11
            end = owner.source_bytes.find(b" meses de servicio.", months) if middle >= 0 else -1
            valid = (start >= 0 and days < middle <= days + 3 and months < end <= months + 3
                     and owner.source_bytes[days:middle].isdigit() and owner.source_bytes[months:end].isdigit())
            if valid:
                owner.candidate = owner.source_bytes[start:end + 19]
                owner.result_code = "CANDIDATE"
            else:
                owner.candidate, owner.result_code = b"", "NO_EVIDENCE"
            # Count the complete candidate representation, not only the fragment.
            owner.output_bytes = len(owner.candidate) + len(owner.result_code.encode("ascii")) + 1
            owner.output_units = owner.output_bytes
            require(instant(self.clock()) < owner.metadata["expires_at_us"], "deadline_exceeded")
        finally:
            owner = None
