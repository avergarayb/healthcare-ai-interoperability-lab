package lab.healthcare.fhir.modelboundary;

import lab.healthcare.fhir.agentstub.AgentStub;
import lab.healthcare.fhir.agentstub.AgentStubObservation;
import lab.healthcare.fhir.agentstub.ObservedCollection;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import java.lang.reflect.RecordComponent;
import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Shared v1 contract guarantees for any destination. Tests pass destination
 * names; this helper does not switch on vendor.
 */
final class ModelBoundaryContractAssertions {

    private ModelBoundaryContractAssertions() {
    }

    static AgentStubObservation assertSharedV1(ModelBoundaryContract contract) {
        assertThat(contract.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(contract.patient()).isNotNull();
        assertThat(contract.patient().resourceType()).isEqualTo("Patient");
        assertThat(contract.conditions()).isNotNull();
        assertThat(contract.observations()).isNotNull();
        assertThat(contract.diagnosticReports()).isNotNull();
        assertAllowlist();
        assertThat(contract.toString()).doesNotContain("Patient/");
        assertThat(contract.toString()).doesNotContain("access_token");

        AgentStubObservation observation = AgentStub.observe(contract);
        assertThat(observation.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(observation.consumed()).isTrue();
        assertThat(observation.modelCalled()).isFalse();
        assertThat(observation.patientStatus()).isEqualTo(contract.patient().status());
        assertMatchingCollection(observation.conditions(), contract.conditions());
        assertMatchingCollection(observation.observations(), contract.observations());
        assertMatchingCollection(observation.diagnosticReports(), contract.diagnosticReports());
        if (contract.medicationRequests() == null) {
            assertThat(observation.medicationRequests()).isNull();
        } else {
            assertMatchingCollection(observation.medicationRequests(), contract.medicationRequests());
        }
        assertThat(observation.toString()).doesNotContain("active");
        assertThat(observation.toString()).doesNotContain("final");
        assertThat(observation.toString()).doesNotContain("order");
        return observation;
    }

    static void assertAllowlist() {
        assertThat(componentNames(BoundaryPatient.class)).containsExactly("status", "resourceType");
        assertThat(componentNames(BoundaryCondition.class)).containsExactly("resourceType", "clinicalStatusCode");
        assertThat(componentNames(BoundaryObservation.class)).containsExactly("resourceType", "status");
        assertThat(componentNames(BoundaryDiagnosticReport.class)).containsExactly("resourceType", "status");
        assertThat(componentNames(BoundaryMedicationRequest.class)).containsExactly("resourceType", "status", "intent");
        assertThat(componentNames(ModelBoundaryContract.class))
                .doesNotContain("patientId", "bundle", "narrative", "valueQuantity");
    }

    static void assertRetention(BoundaryCollection<?> collection, int received, int retained, boolean truncated) {
        assertThat(collection.status()).isEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
        assertThat(collection.receivedCount()).isEqualTo(received);
        assertThat(collection.retainedCount()).isEqualTo(retained);
        assertThat(collection.truncated()).isEqualTo(truncated);
        if (collection.records() != null && collection.status() == ClinicalSnapshotResourceStatus.SUCCESS) {
            assertThat(collection.records()).hasSize(retained);
        }
    }

    private static void assertMatchingCollection(ObservedCollection observed, BoundaryCollection<?> source) {
        assertThat(observed).isNotNull();
        assertThat(observed.status()).isEqualTo(source.status());
        assertThat(observed.receivedCount()).isEqualTo(source.receivedCount());
        assertThat(observed.retainedCount()).isEqualTo(source.retainedCount());
        assertThat(observed.truncated()).isEqualTo(source.truncated());
    }

    private static List<String> componentNames(Class<?> type) {
        return Arrays.stream(type.getRecordComponents()).map(RecordComponent::getName).toList();
    }
}
