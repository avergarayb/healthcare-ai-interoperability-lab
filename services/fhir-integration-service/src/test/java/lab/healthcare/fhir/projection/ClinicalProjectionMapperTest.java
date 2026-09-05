package lab.healthcare.fhir.projection;

import org.hl7.fhir.r4.model.Address;
import org.hl7.fhir.r4.model.Attachment;
import org.hl7.fhir.r4.model.CodeableConcept;
import org.hl7.fhir.r4.model.Coding;
import org.hl7.fhir.r4.model.Condition;
import org.hl7.fhir.r4.model.ContactPoint;
import org.hl7.fhir.r4.model.DiagnosticReport;
import org.hl7.fhir.r4.model.Dosage;
import org.hl7.fhir.r4.model.HumanName;
import org.hl7.fhir.r4.model.Identifier;
import org.hl7.fhir.r4.model.MedicationRequest;
import org.hl7.fhir.r4.model.Narrative;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Quantity;
import org.hl7.fhir.r4.model.Reference;
import org.junit.jupiter.api.Test;

import java.lang.reflect.RecordComponent;
import java.time.LocalDate;
import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ClinicalProjectionMapperTest {

    @Test
    void patientAllowlistIsOnlyResourceType() {
        assertThat(componentNames(RetainedPatient.class)).containsExactly("resourceType");

        Patient patient = new Patient();
        patient.setId("secret-patient-12724067");
        patient.addName(new HumanName().setFamily("secret-family-name").addGiven("secret-given-name"));
        patient.setBirthDate(java.sql.Date.valueOf(LocalDate.of(1980, 1, 15)));
        patient.addIdentifier(new Identifier().setValue("secret-mrn-999"));
        patient.addAddress(new Address().setCity("secret-city"));
        patient.addTelecom(new ContactPoint().setValue("555-0100"));

        RetainedPatient projected = ClinicalProjectionMapper.patient(patient);

        assertThat(projected.resourceType()).isEqualTo("Patient");
        assertThat(projected.toString()).doesNotContain("secret-patient-12724067");
        assertThat(projected.toString()).doesNotContain("secret-family-name");
        assertThat(projected.toString()).doesNotContain("secret-given-name");
        assertThat(projected.toString()).doesNotContain("1980");
        assertThat(projected.toString()).doesNotContain("secret-mrn-999");
        assertThat(projected.toString()).doesNotContain("secret-city");
        assertThat(projected.toString()).doesNotContain("555-0100");
    }

    @Test
    void conditionAllowlistIsResourceTypeAndClinicalStatusCode() {
        assertThat(componentNames(RetainedCondition.class)).containsExactly("resourceType", "clinicalStatus");

        Condition condition = new Condition();
        condition.setId("secret-condition-440");
        condition.getClinicalStatus().addCoding(new Coding().setCode("active"));
        condition.setCode(new CodeableConcept().addCoding(
                new Coding().setSystem("http://snomed.info/sct").setCode("44054006").setDisplay("Diabetes mellitus")));
        condition.setSubject(new Reference("Patient/secret-patient-12724067"));
        condition.addNote().setText("secret-condition-note");
        condition.getText().setStatus(Narrative.NarrativeStatus.GENERATED).setDivAsString("<div>secret narrative</div>");

        RetainedCondition projected = ClinicalProjectionMapper.condition(condition);

        assertThat(projected.resourceType()).isEqualTo("Condition");
        assertThat(projected.clinicalStatus()).isEqualTo("active");
        assertThat(projected.toString()).doesNotContain("secret-condition-440");
        assertThat(projected.toString()).doesNotContain("44054006");
        assertThat(projected.toString()).doesNotContain("Diabetes");
        assertThat(projected.toString()).doesNotContain("secret-patient-12724067");
        assertThat(projected.toString()).doesNotContain("secret-condition-note");
        assertThat(projected.toString()).doesNotContain("secret narrative");
    }

    @Test
    void observationAllowlistIsResourceTypeAndStatus() {
        assertThat(componentNames(RetainedObservation.class)).containsExactly("resourceType", "status");

        Observation observation = new Observation();
        observation.setId("secret-obs-1");
        observation.setStatus(Observation.ObservationStatus.FINAL);
        observation.setCode(new CodeableConcept().addCoding(
                new Coding().setSystem("http://loinc.org").setCode("2339-0").setDisplay("Glucose")));
        observation.setValue(new Quantity().setValue(197).setUnit("mg/dL"));
        observation.addInterpretation().addCoding(new Coding().setCode("H").setDisplay("High"));
        observation.setSubject(new Reference("Patient/secret-patient-12724067"));
        observation.addNote().setText("secret-obs-note");

        RetainedObservation projected = ClinicalProjectionMapper.observation(observation);

        assertThat(projected.resourceType()).isEqualTo("Observation");
        assertThat(projected.status()).isEqualTo("final");
        assertThat(projected.toString()).doesNotContain("secret-obs-1");
        assertThat(projected.toString()).doesNotContain("2339-0");
        assertThat(projected.toString()).doesNotContain("Glucose");
        assertThat(projected.toString()).doesNotContain("197");
        assertThat(projected.toString()).doesNotContain("secret-obs-note");
        assertThat(projected.toString()).doesNotContain("secret-patient-12724067");
    }

    @Test
    void diagnosticReportAllowlistIsResourceTypeAndStatus() {
        assertThat(componentNames(RetainedDiagnosticReport.class)).containsExactly("resourceType", "status");

        DiagnosticReport report = new DiagnosticReport();
        report.setId("secret-report-1");
        report.setStatus(DiagnosticReport.DiagnosticReportStatus.FINAL);
        report.setCode(new CodeableConcept().setText("secret-report-code"));
        report.getText().setStatus(Narrative.NarrativeStatus.GENERATED).setDivAsString("<div>secret report text</div>");
        report.setConclusion("secret-conclusion");
        report.addPresentedForm(new Attachment().setTitle("secret-attachment"));
        report.setSubject(new Reference("Patient/secret-patient-12724067"));

        RetainedDiagnosticReport projected = ClinicalProjectionMapper.diagnosticReport(report);

        assertThat(projected.resourceType()).isEqualTo("DiagnosticReport");
        assertThat(projected.status()).isEqualTo("final");
        assertThat(projected.toString()).doesNotContain("secret-report-1");
        assertThat(projected.toString()).doesNotContain("secret-report-code");
        assertThat(projected.toString()).doesNotContain("secret report text");
        assertThat(projected.toString()).doesNotContain("secret-conclusion");
        assertThat(projected.toString()).doesNotContain("secret-attachment");
        assertThat(projected.toString()).doesNotContain("secret-patient-12724067");
    }

    @Test
    void medicationRequestAllowlistIsResourceTypeStatusAndIntent() {
        assertThat(componentNames(RetainedMedicationRequest.class))
                .containsExactly("resourceType", "status", "intent");

        MedicationRequest request = new MedicationRequest();
        request.setId("secret-med-1");
        request.setStatus(MedicationRequest.MedicationRequestStatus.ACTIVE);
        request.setIntent(MedicationRequest.MedicationRequestIntent.ORDER);
        request.setMedication(new CodeableConcept().addCoding(
                new Coding().setCode("860975").setDisplay("secret-metformin")));
        request.addDosageInstruction(new Dosage().setText("secret-dose-500mg"));
        request.setSubject(new Reference("Patient/secret-patient-12724067"));

        RetainedMedicationRequest projected = ClinicalProjectionMapper.medicationRequest(request);

        assertThat(projected.resourceType()).isEqualTo("MedicationRequest");
        assertThat(projected.status()).isEqualTo("active");
        assertThat(projected.intent()).isEqualTo("order");
        assertThat(projected.toString()).doesNotContain("secret-med-1");
        assertThat(projected.toString()).doesNotContain("860975");
        assertThat(projected.toString()).doesNotContain("secret-metformin");
        assertThat(projected.toString()).doesNotContain("secret-dose-500mg");
        assertThat(projected.toString()).doesNotContain("secret-patient-12724067");
    }

    private static List<String> componentNames(Class<?> type) {
        return Arrays.stream(type.getRecordComponents()).map(RecordComponent::getName).toList();
    }
}
