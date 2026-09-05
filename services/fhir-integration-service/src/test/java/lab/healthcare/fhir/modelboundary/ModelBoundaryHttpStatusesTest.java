package lab.healthcare.fhir.modelboundary;

import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ModelBoundaryHttpStatusesTest {

    @Test
    void matchesLaboratoryHttpMapping() {
        assertThat(ModelBoundaryHttpStatuses.of(ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE)).isEqualTo(200);
        assertThat(ModelBoundaryHttpStatuses.of(ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL)).isEqualTo(200);
        assertThat(ModelBoundaryHttpStatuses.of(ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED)).isEqualTo(401);
        assertThat(ModelBoundaryHttpStatuses.of(ClinicalSnapshotOutcome.PATIENT_CONTEXT_NOT_CONFIGURED)).isEqualTo(409);
        assertThat(ModelBoundaryHttpStatuses.of(ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE)).isEqualTo(502);
    }
}
