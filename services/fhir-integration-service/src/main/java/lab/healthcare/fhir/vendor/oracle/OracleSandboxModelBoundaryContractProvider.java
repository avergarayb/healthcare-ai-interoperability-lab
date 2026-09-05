package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractProvider;

import org.springframework.stereotype.Component;

/**
 * Supplies the current v1 contract from the Oracle sandbox projection. Does
 * not invent a second FHIR fetch or an Oracle-specific contract type.
 */
@Component
public class OracleSandboxModelBoundaryContractProvider implements ModelBoundaryContractProvider {

    private final OracleSandboxModelBoundaryService modelBoundaryService;
    private final OracleHealthIntegrationProfile profile;

    public OracleSandboxModelBoundaryContractProvider(
            OracleSandboxModelBoundaryService modelBoundaryService,
            OracleHealthIntegrationProfile profile) {
        if (modelBoundaryService == null) {
            throw new IllegalArgumentException("Oracle sandbox model boundary service must be provided");
        }
        if (profile == null) {
            throw new IllegalArgumentException("Oracle Health integration profile must be provided");
        }
        this.modelBoundaryService = modelBoundaryService;
        this.profile = profile;
    }

    @Override
    public ModelBoundaryContract currentContract() {
        return modelBoundaryService.assemble(profile);
    }
}
