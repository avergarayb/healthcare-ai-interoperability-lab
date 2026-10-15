package lab.healthcare.fhir.vendor;

import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractVersion;
import lab.healthcare.fhir.modelboundary.ModelBoundaryMapper;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.projection.ClinicalProjectionResult;
import lab.healthcare.fhir.projection.ProjectedCollection;
import lab.healthcare.fhir.projection.RetainedCondition;
import lab.healthcare.fhir.projection.RetainedDiagnosticReport;
import lab.healthcare.fhir.projection.RetainedMedicationRequest;
import lab.healthcare.fhir.projection.RetainedObservation;
import lab.healthcare.fhir.projection.RetainedPatient;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;
import lab.healthcare.fhir.vendor.epic.EpicIntegrationProfile;
import lab.healthcare.fhir.vendor.epic.EpicSandboxClinicalProjectionService;
import lab.healthcare.fhir.vendor.oracle.OracleHealthIntegrationProfile;
import lab.healthcare.fhir.vendor.oracle.OracleSandboxModelBoundaryService;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ConfiguredDestinationModelBoundaryTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T19:20:00Z");

    @Mock
    private EpicSandboxClinicalProjectionService epicProjection;

    @Mock
    private EpicIntegrationProfile epicProfile;

    @Mock
    private OracleSandboxModelBoundaryService oracleModelBoundary;

    @Mock
    private OracleHealthIntegrationProfile oracleProfile;

    @Mock
    private LocalHapiModelBoundary localHapi;

    @Test
    void epicDestinationReusesEpicProjectionWithoutMedicationRequests() {
        ClinicalProjectionResult projection = projection("epic-sandbox", null);
        when(epicProjection.assemble(epicProfile)).thenReturn(projection);

        ModelBoundaryContract contract = source("epic-sandbox").currentContract();

        assertThat(contract.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(contract.destination()).isEqualTo("epic-sandbox");
        assertThat(contract.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE);
        assertThat(contract.medicationRequests()).isNull();
        assertThat(contract.conditions().records()).hasSize(1);
        verify(epicProjection).assemble(epicProfile);
        verifyNoInteractions(oracleModelBoundary, localHapi);
    }

    @Test
    void oracleDestinationReusesOracleModelBoundary() {
        ModelBoundaryContract assembled = ModelBoundaryMapper.from(
                projection(
                        "oracle-health-sandbox",
                        ProjectedCollection.retained(
                                1,
                                1,
                                false,
                                List.of(new RetainedMedicationRequest("MedicationRequest", "active", "order")))));
        when(oracleModelBoundary.assemble(oracleProfile)).thenReturn(assembled);

        ModelBoundaryContract contract = source("oracle-health-sandbox").currentContract();

        assertThat(contract).isSameAs(assembled);
        assertThat(contract.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(contract.medicationRequests()).isNotNull();
        assertThat(contract.medicationRequests().records()).hasSize(1);
        verify(oracleModelBoundary).assemble(oracleProfile);
        verifyNoInteractions(epicProjection, localHapi);
    }

    @Test
    void localHapiDestinationReusesLocalAdapter() {
        ModelBoundaryContract assembled = ModelBoundaryMapper.from(projection(
                "local-hapi",
                ProjectedCollection.retained(
                        1, 1, false, List.of(new RetainedMedicationRequest("MedicationRequest", "active", "order")))));
        when(localHapi.currentContract()).thenReturn(assembled);

        ModelBoundaryContract contract = source("local-hapi").currentContract();

        assertThat(contract).isSameAs(assembled);
        assertThat(contract.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(contract.medicationRequests()).isNotNull();
        verify(localHapi).currentContract();
        verifyNoInteractions(epicProjection, oracleModelBoundary);
    }

    @ParameterizedTest
    @ValueSource(strings = {"example-org", "secured-lab", "smart-lab", "unknown"})
    void unsupportedDestinationFailsClosedBeforeFhirReads(String destination) {
        ModelBoundaryContract contract = source(destination).currentContract();

        assertThat(contract.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(contract.destination()).isEqualTo(destination);
        assertThat(contract.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE);
        assertThat(contract.patient()).isNull();
        assertThat(contract.conditions()).isNull();
        assertThat(contract.observations()).isNull();
        assertThat(contract.diagnosticReports()).isNull();
        assertThat(contract.medicationRequests()).isNull();
        verifyNoInteractions(epicProjection, oracleModelBoundary, localHapi);
    }

    private ConfiguredDestinationModelBoundary source(String activeServer) {
        return new ConfiguredDestinationModelBoundary(
                new FhirServersProperties(activeServer, Map.of()),
                epicProjection,
                epicProfile,
                oracleModelBoundary,
                oracleProfile,
                localHapi);
    }

    private static ClinicalProjectionResult projection(
            String destination, ProjectedCollection<RetainedMedicationRequest> medicationRequests) {
        return new ClinicalProjectionResult(
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                destination,
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotResourceStatus.SUCCESS,
                new RetainedPatient("Patient"),
                ProjectedCollection.retained(1, 1, false, List.of(new RetainedCondition("Condition", "active"))),
                ProjectedCollection.retained(1, 1, false, List.of(new RetainedObservation("Observation", "final"))),
                ProjectedCollection.retained(
                        1, 1, false, List.of(new RetainedDiagnosticReport("DiagnosticReport", "final"))),
                medicationRequests,
                "");
    }
}
