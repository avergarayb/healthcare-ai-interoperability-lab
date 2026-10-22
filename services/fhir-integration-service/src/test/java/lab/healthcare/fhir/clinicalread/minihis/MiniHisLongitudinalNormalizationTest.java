package lab.healthcare.fhir.clinicalread.minihis;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class MiniHisLongitudinalNormalizationTest {

    private final ObjectMapper json = new ObjectMapper();
    private final MiniHisNormalizer normalizer = new MiniHisNormalizer(json);

    @Test
    void finishedVisitWithoutEndOmitsPeriodEndAndKeepsLegacyCopy() {
        ObjectNode open = normalizer.encounter(json.createObjectNode()
                .put("consultationId", "MHS-CON-020")
                .put("patientId", "MHS-PAT-011")
                .put("occurredAt", "2026-04-01T10:00:00Z")
                .put("status", "completed")
                .put("careClass", "ambulatory")
                .putNull("endedAt"));
        assertThat(open.path("status").asText()).isEqualTo("finished");
        assertThat(open.path("period").has("end")).isFalse();
        assertThat(open.path("meta").path("source").asText()).isEqualTo(MiniHisNormalizer.SOURCE);

        ObjectNode legacy = normalizer.encounter(json.createObjectNode()
                .put("consultationId", "MHS-CON-015")
                .put("patientId", "MHS-PAT-006")
                .put("occurredAt", "2026-06-01T10:00:00Z")
                .put("status", "completed")
                .put("careClass", "ambulatory"));
        assertThat(legacy.path("period").path("end").asText()).isEqualTo("2026-06-01T10:00:00Z");
    }

    @Test
    void newStatusesAndIncompleteRowsStayExplicit() {
        ObjectNode planned = normalizer.encounter(json.createObjectNode()
                .put("consultationId", "MHS-CON-028")
                .put("patientId", "MHS-PAT-015")
                .put("occurredAt", "2026-12-01T10:00:00Z")
                .put("status", "scheduled")
                .put("careClass", "ambulatory")
                .putNull("endedAt"));
        assertThat(planned.path("status").asText()).isEqualTo("planned");
        assertThat(planned.path("period").has("end")).isFalse();

        ObjectNode missingIssued = normalizer.observation(json.createObjectNode()
                .put("resultId", "MHS-RES-019")
                .put("consultationId", "MHS-CON-019")
                .put("patientId", "MHS-PAT-010")
                .put("resultType", "laboratory")
                .put("displayName", "Hemoglobina")
                .put("valueText", "11.0")
                .put("unit", "g/dL")
                .putNull("observedAt")
                .put("status", "final"));
        assertThat(missingIssued.has("issued")).isFalse();
        assertThat(missingIssued.path("encounter").path("reference").asText()).isEqualTo("Encounter/MHS-CON-019");

        ObjectNode corrected = normalizer.observation(json.createObjectNode()
                .put("resultId", "MHS-RES-025")
                .put("consultationId", "MHS-CON-023")
                .put("patientId", "MHS-PAT-014")
                .put("resultType", "laboratory")
                .put("displayName", "Hemoglobina")
                .put("valueText", "10.4")
                .put("unit", "g/dL")
                .put("observedAt", "2026-01-15T12:00:00Z")
                .put("status", "corrected"));
        assertThat(corrected.path("status").asText()).isEqualTo("corrected");

        ObjectNode appointment = normalizer.appointment(json.createObjectNode()
                .put("appointmentId", "MHS-APT-011")
                .put("patientId", "MHS-PAT-007")
                .put("status", "confirmed")
                .put("start", "2099-01-01T12:00:00Z")
                .put("replacesAppointmentId", "MHS-APT-010"));
        assertThat(appointment.path("status").asText()).isEqualTo("booked");
        assertThat(appointment.path("extension").get(0).path("url").asText())
                .isEqualTo(MiniHisNormalizer.REPLACES_APPOINTMENT);
        assertThat(appointment.path("extension").get(0).path("valueReference").path("reference").asText())
                .isEqualTo("Appointment/MHS-APT-010");

        ObjectNode undated = normalizer.appointment(json.createObjectNode()
                .put("appointmentId", "MHS-APT-013")
                .put("patientId", "MHS-PAT-009")
                .put("status", "not_attended")
                .putNull("start"));
        assertThat(undated.path("status").asText()).isEqualTo("noshow");
        assertThat(undated.has("start")).isFalse();

        assertThat(normalizer.appointment(json.createObjectNode()
                .put("appointmentId", "MHS-APT-012")
                .put("patientId", "MHS-PAT-008")
                .put("status", "cancelled")
                .put("start", "2020-01-01T12:00:00Z")).path("status").asText()).isEqualTo("cancelled");
        assertThat(normalizer.appointment(json.createObjectNode()
                .put("appointmentId", "MHS-APT-023")
                .put("patientId", "MHS-PAT-015")
                .put("status", "completed")
                .put("start", "2020-01-01T12:00:00Z")).path("status").asText()).isEqualTo("fulfilled");

        assertThatThrownBy(() -> normalizer.appointment(json.createObjectNode()
                .put("appointmentId", "MHS-APT-011")
                .put("patientId", "MHS-PAT-007")
                .put("status", "confirmed")
                .put("start", "not-a-date")))
                .isInstanceOf(ClinicalReadException.class)
                .extracting(ex -> ((ClinicalReadException) ex).code())
                .isEqualTo("invalid_source");
    }
}
