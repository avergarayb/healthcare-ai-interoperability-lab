package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryMapper;

import org.springframework.stereotype.Component;

/**
 * Maps one Task 042 projection onto the vendor-neutral v1 model boundary. Does
 * not assemble FHIR again, invent an Oracle contract, or call a model.
 */
@Component
public class OracleSandboxModelBoundaryService {

    private final OracleSandboxClinicalProjectionService projectionService;

    public OracleSandboxModelBoundaryService(OracleSandboxClinicalProjectionService projectionService) {
        if (projectionService == null) {
            throw new IllegalArgumentException("Oracle sandbox clinical projection service must be provided");
        }
        this.projectionService = projectionService;
    }

    public ModelBoundaryContract assemble(OracleHealthIntegrationProfile profile) {
        return ModelBoundaryMapper.from(projectionService.assemble(profile));
    }
}
