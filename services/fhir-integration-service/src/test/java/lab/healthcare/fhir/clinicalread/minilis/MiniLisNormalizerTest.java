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
        assertThat(observation.path("valueQuantity").path("system").asText()).isEqualTo("http://unitsofmeasure.org");
        assertThat(observation.path("valueQuantity").path("code").asText()).isEqualTo("g/dL");
        assertThat(observation.path("referenceRange").get(0).path("low").path("value").decimalValue())
                .isEqualByComparingTo("12.0");
        assertThat(observation.path("referenceRange").get(0).path("high").path("value").decimalValue())
                .isEqualByComparingTo("16.0");
        assertThat(observation.path("referenceRange").get(0).path("low").path("code").asText()).isEqualTo("g/dL");
        assertThat(observation.path("referenceRange").get(0).has("text")).isFalse();
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
    void codesSeedGlucoseAndLeavesAnUnmappedUnitUncoded() throws Exception {
        ObjectNode glucose = normalizer.observation(json.readTree("""
                {"resultId":"MLS-RES-003","orderId":"MLS-ORD-003","patientId":"MLS-PAT-003","externalResultId":"EXT-RES-003","testCode":"GLU","value":"90","unit":"mg/dL","referenceRange":"70-99","resultedAt":"2026-02-03T12:00:00Z","status":"FINAL"}
                """));
        assertThat(glucose.path("valueQuantity").path("value").decimalValue()).isEqualByComparingTo("90");
        assertThat(glucose.path("valueQuantity").path("unit").asText()).isEqualTo("mg/dL");
        assertThat(glucose.path("valueQuantity").path("system").asText()).isEqualTo("http://unitsofmeasure.org");
        assertThat(glucose.path("valueQuantity").path("code").asText()).isEqualTo("mg/dL");
        assertThat(glucose.path("referenceRange").get(0).path("low").path("value").decimalValue()).isEqualByComparingTo("70");
        assertThat(glucose.path("referenceRange").get(0).path("high").path("unit").asText()).isEqualTo("mg/dL");

        ObjectNode uncoded = normalizer.observation(json.readTree("""
                {"resultId":"MLS-RES-141","orderId":"MLS-ORD-141","patientId":"MLS-PAT-003","externalResultId":"EXT-RES-141","testCode":"GLU","value":"141","unit":"mmol/L","referenceRange":"70-110","resultedAt":"2026-02-03T12:00:00Z","status":"FINAL"}
                """));
        assertThat(uncoded.path("valueQuantity").path("value").decimalValue()).isEqualByComparingTo("141");
        assertThat(uncoded.path("valueQuantity").path("unit").asText()).isEqualTo("mmol/L");
        assertThat(uncoded.path("valueQuantity").has("system")).isFalse();
        assertThat(uncoded.path("valueQuantity").has("code")).isFalse();
        assertThat(uncoded.path("referenceRange").get(0).path("text").asText()).isEqualTo("70-110");

        ObjectNode reversed = normalizer.observation(json.readTree("""
                {"resultId":"MLS-RES-REV","orderId":"MLS-ORD-003","patientId":"MLS-PAT-003","externalResultId":"EXT-RES-REV","testCode":"GLU","value":"90","unit":"mg/dL","referenceRange":"99-70","resultedAt":"2026-02-03T12:00:00Z","status":"FINAL"}
                """));
        assertThat(reversed.path("valueQuantity").has("system")).isFalse();
        assertThat(reversed.path("referenceRange").get(0).path("text").asText()).isEqualTo("99-70");
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
    void keepsTheIssuerSystemInsteadOfTheLaboratoryConstant() throws Exception {
        ObjectNode patient = normalizer.patient(json.readTree("""
                {"patientId":"MLS-PAT-020","organizationId":"org-mini-his","externalId":"CASE-020","identifierSystem":"https://lab.local/other-system/patient","familyName":"Nunez","givenName":"Oscar","birthDate":"1970-01-01","administrativeSex":"male"}
                """));
        assertThat(patient.path("identifier").findValuesAsText("system"))
                .contains("https://lab.local/other-system/patient")
                .doesNotContain("https://lab.local/mini-lis/organization/org-mini-his/patient");
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
