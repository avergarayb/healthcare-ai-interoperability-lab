package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractVersion;
import lab.healthcare.fhir.projection.ClinicalProjectionAssembler;
import lab.healthcare.fhir.projection.ClinicalProjectionResult;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class OracleSandboxModelBoundaryServiceTest {

    private static final String SECRET = "oracle-live-access-token";
    private static final String PATIENT_ID = "lab-configured-patient";

    @Mock
    private OracleSandboxClinicalProjectionService projectionService;

    @Mock
    private ClinicalProjectionAssembler assembler;

    @Test
    void mapsOneProjectionWithoutAssemblingFhirAgain() {
        ClinicalProjectionResult projection = ClinicalProjectionResult.authenticationRequired(
                "oracle-health-sandbox", "No usable access token");
        when(projectionService.assemble(any())).thenReturn(projection);

        ModelBoundaryContract contract =
                service().assemble(OracleHealthIntegrationProfileTest.completePublicPkceEnabled());

        assertThat(contract.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(contract.outcome()).isEqualTo(ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED);
        assertThat(contract.toString()).doesNotContain(SECRET);
        assertThat(contract.toString()).doesNotContain(PATIENT_ID);
        verify(projectionService).assemble(any());
        verify(assembler, never()).assemble(any(), any(), any(), any());
    }

    @Test
    void contextNotConfiguredIsMappedWithoutAssembler() {
        when(projectionService.assemble(any()))
                .thenReturn(ClinicalProjectionResult.contextNotConfigured("oracle-health-sandbox"));

        ModelBoundaryContract contract =
                service().assemble(OracleHealthIntegrationProfileTest.completePublicPkceEnabled());

        assertThat(contract.outcome()).isEqualTo(ClinicalSnapshotOutcome.PATIENT_CONTEXT_NOT_CONFIGURED);
        verify(assembler, never()).assemble(any(), any(), any(), any());
    }

    private OracleSandboxModelBoundaryService service() {
        return new OracleSandboxModelBoundaryService(projectionService);
    }
}
