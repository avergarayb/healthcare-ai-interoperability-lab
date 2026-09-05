package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryMapper;
import lab.healthcare.fhir.projection.ClinicalProjectionResult;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class OracleSandboxModelBoundaryContractProviderTest {

    @Mock
    private OracleSandboxModelBoundaryService modelBoundaryService;

    @Test
    void currentContractReusesOneProjectionAssembly() {
        OracleHealthIntegrationProfile profile = OracleHealthIntegrationProfileTest.completePublicPkceEnabled();
        ModelBoundaryContract assembled = ModelBoundaryMapper.from(
                ClinicalProjectionResult.authenticationRequired("oracle-health-sandbox", "No usable access token"));
        when(modelBoundaryService.assemble(eq(profile))).thenReturn(assembled);

        ModelBoundaryContract contract =
                new OracleSandboxModelBoundaryContractProvider(modelBoundaryService, profile).currentContract();

        assertThat(contract).isSameAs(assembled);
        assertThat(contract.outcome()).isEqualTo(ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED);
        verify(modelBoundaryService).assemble(profile);
    }
}
