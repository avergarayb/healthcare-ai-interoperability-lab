package lab.healthcare.fhir.clinicalread.minilis;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.hl7.fhir.r4.model.DiagnosticReport;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.ServiceRequest;
import org.junit.jupiter.api.Test;

import ca.uhn.fhir.context.FhirContext;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class MiniLisNormalizerTest {

    private static final FhirContext FHIR = FhirContext.forR4();
    private final ObjectMapper json = new ObjectMapper();
    private final MiniLisNormalizer normalizer = new MiniLisNormalizer(json);

    @Test
    void mapsPatientOrderObservationAndReportWithProprietaryCodes() throws Exception {
        ObjectNode patient = normalizer.patient(json.readTree("""
                {"patientId":"MLS-PAT-002","organizationId":"org-mini-lis","externalId":"EXT-PAT-002","familyName":"Ramos","givenName":"Luis","birthDate":"1978-06-02","administrativeSex":"male"}
                """));
        ObjectNode order = normalizer.serviceRequest(json.readTree("""
                {"orderId":"MLS-ORD-002","patientId":"MLS-PAT-002","requestingOrganizationId":"org-mini-his","externalRequestId":"EXT-REQ-002","testCode":"HGB","testDescription":"Hemoglobin","requestedAt":"2026-02-02T10:00:00Z","status":"COMPLETED"}
                """));
        ObjectNode observation = normalizer.observation(json.readTree("""
                {"resultId":"MLS-RES-002","orderId":"MLS-ORD-002","patientId":"MLS-PAT-002","externalResultId":"EXT-RES-002","testCode":"HGB","value":"13.5","unit":"g/dL","referenceRange":"12.0-16.0","resultedAt":"2026-02-02T12:00:00Z","status":"FINAL"}
                """));
        ArrayNode results = json.createArrayNode().add(json.readTree("""
                {"resultId":"MLS-RES-002","orderId":"MLS-ORD-002","patientId":"MLS-PAT-002","externalResultId":"EXT-RES-002","testCode":"HGB","value":"13.5","unit":"g/dL","resultedAt":"2026-02-02T12:00:00Z","status":"FINAL"}
                """));
        ObjectNode orderSource = (ObjectNode) json.readTree("""
                {"orderId":"MLS-ORD-002","patientId":"MLS-PAT-002","requestingOrganizationId":"org-mini-his","externalRequestId":"EXT-REQ-002","testCode":"HGB","testDescription":"Hemoglobin","requestedAt":"2026-02-02T10:00:00Z","status":"COMPLETED"}
                """);
        ObjectNode report = normalizer.diagnosticReport(orderSource, results, "MLS-PAT-002");

        assertThat(patient.path("identifier").findValuesAsText("system"))
                .contains(MiniLisNormalizer.PATIENT_SYSTEM, "https://lab.local/mini-lis/organization/org-mini-lis/patient");
        assertThat(patient.path("managingOrganization").path("identifier").path("value").asText()).isEqualTo("org-mini-lis");
        assertThat(order.path("status").asText()).isEqualTo("completed");
        assertThat(order.path("subject").path("reference").asText()).isEqualTo("Patient/MLS-PAT-002");
        assertThat(order.path("code").path("coding").get(0).path("system").asText()).isEqualTo(MiniLisNormalizer.TEST_SYSTEM);
        assertThat(order.path("code").path("coding").get(0).path("code").asText()).isEqualTo("HGB");
        assertThat(order.toString()).doesNotContain("loinc");
        assertThat(observation.path("valueQuantity").path("value").decimalValue()).isEqualByComparingTo("13.5");
        assertThat(observation.path("valueQuantity").path("unit").asText()).isEqualTo("g/dL");
        assertThat(observation.path("valueQuantity").has("system")).isFalse();
        assertThat(observation.path("basedOn").get(0).path("reference").asText()).isEqualTo("ServiceRequest/MLS-ORD-002");
        assertThat(observation.path("status").asText()).isEqualTo("final");
        assertThat(report.path("status").asText()).isEqualTo("final");
        assertThat(report.path("result").get(0).path("reference").asText()).isEqualTo("Observation/MLS-RES-002");
        assertThat(report.path("basedOn").get(0).path("reference").asText()).isEqualTo("ServiceRequest/MLS-ORD-002");

        FHIR.newJsonParser().parseResource(Patient.class, patient.toString());
        FHIR.newJsonParser().parseResource(ServiceRequest.class, order.toString());
        FHIR.newJsonParser().parseResource(Observation.class, observation.toString());
        FHIR.newJsonParser().parseResource(DiagnosticReport.class, report.toString());
    }

    @Test
    void keepsANonNumericValueAsTextAndRejectsAMissingField() throws Exception {
        ObjectNode observation = normalizer.observation(json.readTree("""
                {"resultId":"MLS-RES-010","orderId":"MLS-ORD-010","patientId":"MLS-PAT-010","externalResultId":"EXT-RES-010","testCode":"NOTE","value":"yellow","unit":"","resultedAt":"2026-02-02T12:00:00Z","status":"PRELIMINARY"}
                """));
        assertThat(observation.path("valueString").asText()).isEqualTo("yellow");
        assertThat(observation.has("valueQuantity")).isFalse();
        assertThat(observation.path("status").asText()).isEqualTo("preliminary");

        assertThatThrownBy(() -> normalizer.serviceRequest(json.readTree("""
                {"orderId":"MLS-ORD-010","patientId":"MLS-PAT-010","status":"ORDERED"}
                """)))
                .isInstanceOf(ClinicalReadException.class)
                .hasMessage("invalid_source");
    }

    @Test
    void mapsOrderStatusesWithoutTreatingCancellationAsCompletion() {
        assertThat(MiniLisNormalizer.serviceRequestStatus("ORDERED")).isEqualTo("active");
        assertThat(MiniLisNormalizer.serviceRequestStatus("CANCELLED")).isEqualTo("revoked");
        assertThat(MiniLisNormalizer.reportStatus("ORDERED")).isEqualTo("registered");
        assertThat(MiniLisNormalizer.reportStatus("IN_PROGRESS")).isEqualTo("partial");
        assertThat(MiniLisNormalizer.observationStatus("CANCELLED")).isEqualTo("cancelled");
    }
}
