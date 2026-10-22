"""Clinical Context Intelligence reads relations that the context already carries.

The protocol result is copied. These tests do not add a clinical rule.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.clinical_context_intelligence import (
    ProtocolVerdict,
    analyze_clinical_context,
    narrative_brief,
    render_intelligence_html,
)
from app.followup_review import FollowUpReviewCaseService
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.longitudinal_context import LongitudinalContext, LongitudinalFact, LongitudinalGap
from app.missed_follow_up_narrative import generate_operational_narrative
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
)


NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)
SOURCE = "https://lab.local/mini-his"


def test_cci_01_linked_final_result_keeps_the_protocol_match():
    analysis = _analyze(
        "SYN-FOLLOWUP-015",
        encounters=(_encounter("MHS-CON-015", "2026-06-01T10:00:00Z", end="2026-06-01T10:00:00Z"),),
        observations=(_observation("MHS-RES-015", "final", "2026-06-01T12:00:00Z", "MHS-CON-015", "12.1 g/dL"),),
        protocol=_verdict("matched", ["post_consultation_result_requires_review"], ["Encounter/MHS-CON-015", "Observation/MHS-RES-015"]),
    )
    assert analysis.operational.evaluation_status == "matched"
    assert _codes(analysis, "confirmed") >= {"observation_encounter", "observation_issued_after_encounter_end"}
    assert "12.1 g/dL" not in str(narrative_brief(analysis))


def test_cci_02_missed_appointment_with_confirmed_replacement():
    analysis = _analyze(
        "SYN-FOLLOWUP-016",
        appointments=(
            _appointment("MHS-APT-010", "noshow", "2025-09-16T12:00:00Z"),
            _appointment("MHS-APT-011", "booked", "2027-11-24T12:00:00Z", replaces="MHS-APT-010"),
        ),
        protocol=_verdict("not_matched", ["confirmed_future_follow_up_exists"], ["Appointment/MHS-APT-010", "Appointment/MHS-APT-011"]),
        evaluated_at=NOW,
    )
    assert analysis.operational.evaluation_status == "not_matched"
    assert "appointment_replaces" in _codes(analysis, "confirmed")
    assert "future_booked_appointment" in _codes(analysis, "confirmed")


def test_cci_03_preliminary_then_final_requires_the_same_encounter():
    linked = _analyze(
        "SYN-FOLLOWUP-022",
        encounters=(_encounter("MHS-CON-022", "2026-02-01T10:00:00Z", end="2026-02-01T10:00:00Z"),),
        observations=(
            _observation("MHS-RES-022A", "preliminary", "2026-02-01T11:00:00Z", "MHS-CON-022"),
            _observation("MHS-RES-022", "final", "2026-02-01T12:00:00Z", "MHS-CON-022"),
        ),
        protocol=_verdict("matched", ["post_consultation_result_requires_review"], ["Encounter/MHS-CON-022", "Observation/MHS-RES-022"]),
    )
    assert "preliminary_then_final" in _codes(linked, "confirmed")
    separate = _analyze(
        "SYN-FOLLOWUP-022",
        encounters=(
            _encounter("MHS-CON-022", "2026-02-01T10:00:00Z", end="2026-02-01T10:00:00Z"),
            _encounter("MHS-CON-099", "2026-02-01T10:30:00Z", end="2026-02-01T10:30:00Z"),
        ),
        observations=(
            _observation("MHS-RES-022A", "preliminary", "2026-02-01T11:00:00Z", "MHS-CON-022"),
            _observation("MHS-RES-022", "final", "2026-02-01T12:00:00Z", "MHS-CON-099"),
        ),
    )
    assert "preliminary_then_final" not in _codes(separate, "confirmed")


def test_cci_04_corrected_result_does_not_change_an_insufficient_protocol():
    analysis = _analyze(
        "SYN-FOLLOWUP-023",
        encounters=(_encounter("MHS-CON-023", "2026-01-15T10:00:00Z", end="2026-01-15T10:00:00Z"),),
        observations=(
            _observation("MHS-RES-024", "preliminary", "2026-01-15T11:00:00Z", "MHS-CON-023"),
            _observation("MHS-RES-025", "corrected", "2026-01-15T12:00:00Z", "MHS-CON-023"),
        ),
        protocol=_verdict("insufficient", ["final_observation_missing"], []),
    )
    assert analysis.operational.evaluation_status == "insufficient"
    assert "preliminary_then_corrected" in _codes(analysis, "confirmed")
    assert "preliminary_then_final" not in _codes(analysis, "confirmed")


def test_cci_05_several_encounters_stay_separate():
    analysis = _analyze(
        "SYN-FOLLOWUP-024",
        encounters=(
            _encounter("MHS-CON-024", "2024-06-01T10:00:00Z", end="2024-06-01T10:00:00Z"),
            _encounter("MHS-CON-025", "2025-06-01T10:00:00Z", end="2025-06-01T10:00:00Z"),
        ),
        observations=(
            _observation("MHS-RES-026", "final", "2024-06-01T12:00:00Z", "MHS-CON-024"),
            _observation("MHS-RES-028", "final", "2025-06-01T13:00:00Z", "MHS-CON-025"),
        ),
    )
    confirmed = [item for item in analysis.relations if item.code == "observation_encounter"]
    assert len(confirmed) == 2
    assert "preliminary_then_final" not in _codes(analysis, "confirmed")


def test_cci_06_missing_references_are_not_inferred_from_time():
    analysis = _analyze(
        "SYN-FOLLOWUP-021",
        encounters=(_encounter("MHS-CON-021", "2026-05-01T10:00:00Z", end="2026-05-01T10:00:00Z"),),
        observations=(_observation("MHS-RES-030", "final", "2026-05-01T11:00:00Z", None),),
        appointments=(_appointment("MHS-APT-030", "noshow", "2026-05-02T12:00:00Z"),),
    )
    assert "observation_without_encounter_reference" in _codes(analysis, "unproven")
    assert "observation_encounter" not in _codes(analysis, "confirmed")
    assert "appointment_replaces" not in _codes(analysis, "confirmed")


def test_cci_07_incomplete_dates_stay_incomplete():
    analysis = _analyze(
        "SYN-FOLLOWUP-020",
        encounters=(_encounter("MHS-CON-020", "2026-04-01T10:00:00Z"),),
        observations=(_observation("MHS-RES-020", "final", "2026-04-01T11:00:00Z", "MHS-CON-020"),),
        appointments=(_appointment("MHS-APT-013", "noshow", None),),
        gaps=(
            LongitudinalGap(code="encounter_end_missing", reference="Encounter/MHS-CON-020"),
            LongitudinalGap(code="appointment_start_missing", reference="Appointment/MHS-APT-013"),
        ),
    )
    assert "observation_timing_end_missing" in _codes(analysis, "incomplete")
    assert "observation_issued_after_encounter_end" not in _codes(analysis, "confirmed")
    assert "encounter_end_missing:Encounter/MHS-CON-020" in analysis.missing
    assert "appointment_start_missing:Appointment/MHS-APT-013" in analysis.missing


def test_cci_08_truncated_context_is_explicit():
    encounters = tuple(_encounter(f"MHS-CON-{index:03d}", f"2024-01-{index:02d}T10:00:00Z", end=f"2024-01-{index:02d}T10:00:00Z") for index in range(1, 13))
    analysis = _analyze(
        "SYN-FOLLOWUP-024",
        encounters=encounters,
        gaps=(LongitudinalGap(code="context_limit_applied"),),
        truncated=True,
    )
    assert analysis.truncated is True
    assert "context_truncated" in analysis.missing
    assert len(analysis.encounters) == 12


def test_cci_09_inconsistent_references_and_dates_are_conflicts():
    analysis = _analyze(
        "SYN-FOLLOWUP-018",
        encounters=(_encounter("MHS-CON-040", "2026-03-01T10:00:00Z", end="2026-03-01T10:00:00Z"),),
        observations=(_observation("MHS-RES-040", "final", "2026-02-01T10:00:00Z", "MHS-CON-040"),),
        appointments=(_appointment("MHS-APT-040", "booked", "2026-03-02T12:00:00Z", replaces="MHS-APT-040"),),
        evaluated_at=NOW,
    )
    conflict_codes = {item.code for item in analysis.conflicts}
    assert "appointment_replaces_self" in conflict_codes
    assert "observation_issued_before_encounter_start" in conflict_codes
    assert "appointment_replaces" not in _codes(analysis, "confirmed")


def test_cci_10_repeated_analysis_and_review_case_stay_stable(tmp_path):
    context = _context("SYN-FOLLOWUP-022", encounters=(_encounter("MHS-CON-022", "2026-02-01T10:00:00Z", end="2026-02-01T10:00:00Z"),))
    protocol = _verdict("matched", ["post_consultation_result_requires_review"], ["Encounter/MHS-CON-022"])
    first = analyze_clinical_context(context, protocol=protocol, evaluated_at=NOW)
    second = analyze_clinical_context(context, protocol=protocol, evaluated_at=NOW)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")

    class Clock:
        def __init__(self) -> None:
            self.value = NOW

        def __call__(self):
            current = self.value
            self.value += timedelta(seconds=1)
            return current

    repository = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3", clock=Clock())
    repository.initialize()
    service = FollowUpReviewCaseService(repository)
    trigger = ProtocolReviewResult(
        id=POST_CONSULTATION_RESULT_REVIEW_V1,
        evaluation_status=ProtocolEvaluationStatus.MATCHED,
        reason_codes=("post_consultation_result_requires_review",),
        matched_resources=("Encounter/MHS-CON-022", "Observation/MHS-RES-022"),
        human_review_status="required",
        human_review_reason="deterministic_post_consultation_protocol_match",
        action_status="proposed",
        action_type="review_follow_up_case",
    )
    opened = service.ensure_for_protocol("SYN-FOLLOWUP-022", trigger)
    repeated = service.ensure_for_protocol("SYN-FOLLOWUP-022", trigger)
    assert opened is not None and repeated is not None
    assert opened.id == repeated.id
    assert repeated.version == 1
    original = "La evidencia leída corresponde a Encounter/MHS-CON-022. El profesional responsable revisa el caso."
    stored = service.record_narrative(opened.id, original)
    kept = service.record_narrative(opened.id, "Texto distinto que no debe reemplazar la narrativa guardada.")
    assert stored.narrative_text == original
    assert kept.narrative_text == original


def test_cci_11_provider_failure_does_not_invent_a_narrative():
    class Broken:
        def generate_structured(self, **_kwargs):
            raise RuntimeError("provider down")

    failed = generate_operational_narrative(
        Broken(),
        matched_resource="Appointment/MHS-APT-001",
        appointments=[{"reference": "Appointment/MHS-APT-001", "status": "noshow", "start": "2025-09-16T12:00:00Z"}],
        longitudinal_brief={"schema": "CLINICAL_CONTEXT_INTELLIGENCE_V1", "truncated": False},
    )
    assert failed.text is None
    assert failed.reason == "provider_unavailable"

    class Invalid:
        error = None
        text = "not-json"

        def generate_structured(self, **_kwargs):
            return self

    invalid = generate_operational_narrative(
        Invalid(),
        matched_resource="Appointment/MHS-APT-001",
        appointments=[],
    )
    assert invalid.text is None
    assert invalid.reason == "invalid_output"


def test_cci_12_longitudinal_patient_keeps_the_copied_protocol_result():
    analysis = _analyze(
        "SYN-FOLLOWUP-024",
        encounters=(
            _encounter("MHS-CON-027", "2023-06-01T10:00:00Z", status="cancelled"),
            _encounter("MHS-CON-024", "2024-06-01T10:00:00Z", end="2024-06-01T10:00:00Z"),
            _encounter("MHS-CON-025", "2025-06-01T10:00:00Z", end="2025-06-01T10:00:00Z"),
            _encounter("MHS-CON-026", "2026-06-01T10:00:00Z", status="in-progress"),
            _encounter("MHS-CON-028", "2026-12-01T10:00:00Z", status="planned"),
        ),
        observations=(
            _observation("MHS-RES-026", "final", "2024-06-01T12:00:00Z", "MHS-CON-024"),
            _observation("MHS-RES-027", "preliminary", "2025-06-01T11:00:00Z", "MHS-CON-025"),
            _observation("MHS-RES-028", "final", "2025-06-01T13:00:00Z", "MHS-CON-025"),
        ),
        appointments=(
            _appointment("MHS-APT-020", "noshow", "2025-09-16T12:00:00Z"),
            _appointment("MHS-APT-021", "booked", "2027-11-24T12:00:00Z", replaces="MHS-APT-020"),
            _appointment("MHS-APT-022", "cancelled", "2026-09-21T12:00:00Z"),
        ),
        protocol=_verdict(
            "not_matched",
            ["upcoming_confirmed_appointment"],
            ["Encounter/MHS-CON-024", "Observation/MHS-RES-026", "Appointment/MHS-APT-021"],
        ),
        evaluated_at=NOW,
    )
    assert analysis.operational.evaluation_status == "not_matched"
    assert analysis.operational.reason_codes == ["upcoming_confirmed_appointment"]
    assert "appointment_replaces" in _codes(analysis, "confirmed")
    assert "future_booked_appointment" in _codes(analysis, "confirmed")
    assert "preliminary_then_final" in _codes(analysis, "confirmed")
    page = render_intelligence_html(analysis)
    assert "Datos provenientes del HIS" in page
    assert "Evaluación determinista" in page
    assert "innecesario" not in page.lower()
    assert "sqlite" not in page.lower()
    source = Path(__file__).resolve().parents[1].joinpath("app", "clinical_context_intelligence.py").read_text(encoding="utf-8")
    assert "evaluate_post_consultation_review" not in source
    assert "evaluate_missed_follow_up" not in source


def _analyze(case_id: str, **kwargs):
    protocol = kwargs.pop("protocol", None)
    evaluated_at = kwargs.pop("evaluated_at", None)
    return analyze_clinical_context(_context(case_id, **kwargs), protocol=protocol, evaluated_at=evaluated_at)


def _context(case_id: str, encounters=(), appointments=(), observations=(), gaps=(), truncated=False) -> LongitudinalContext:
    return LongitudinalContext(
        caseId=case_id,
        patientId="MHS-PAT-015",
        status="partial" if truncated else "complete",
        encounters=list(encounters),
        appointments=list(appointments),
        observations=list(observations),
        gaps=list(gaps),
        truncated=truncated,
    )


def _encounter(resource_id: str, instant: str, end: str | None = None, status: str = "finished") -> LongitudinalFact:
    return LongitudinalFact(
        reference=f"Encounter/{resource_id}",
        status=status,
        instant=instant,
        end=end,
        source=SOURCE,
    )


def _observation(resource_id: str, status: str, instant: str | None, encounter_id: str | None, recorded: str | None = None) -> LongitudinalFact:
    related = [f"Encounter/{encounter_id}"] if encounter_id else []
    return LongitudinalFact(
        reference=f"Observation/{resource_id}",
        status=status,
        instant=instant,
        related=related,
        source=SOURCE,
        recordedValue=recorded,
    )


def _appointment(resource_id: str, status: str, instant: str | None, replaces: str | None = None) -> LongitudinalFact:
    related = [f"Appointment/{replaces}"] if replaces else []
    return LongitudinalFact(
        reference=f"Appointment/{resource_id}",
        status=status,
        instant=instant,
        related=related,
        source=SOURCE,
    )


def _verdict(status: str, reasons: list[str], evidence: list[str]) -> ProtocolVerdict:
    return ProtocolVerdict(
        protocol_id="POST_CONSULTATION_RESULT_REVIEW_V1",
        evaluation_status=status,
        reason_codes=reasons,
        primary_evidence=evidence,
    )


def _codes(analysis, kind: str) -> set[str]:
    return {item.code for item in analysis.relations if item.kind == kind}
