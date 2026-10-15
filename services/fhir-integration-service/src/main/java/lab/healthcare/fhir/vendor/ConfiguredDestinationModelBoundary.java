package lab.healthcare.fhir.vendor;

import lab.healthcare.fhir.modelboundary.ConfiguredModelBoundarySource;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractVersion;
import lab.healthcare.fhir.modelboundary.ModelBoundaryMapper;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.vendor.epic.EpicIntegrationProfile;
import lab.healthcare.fhir.vendor.epic.EpicSandboxClinicalProjectionService;
import lab.healthcare.fhir.vendor.oracle.OracleHealthIntegrationProfile;
import lab.healthcare.fhir.vendor.oracle.OracleSandboxModelBoundaryService;

import org.springframework.stereotype.Component;

/**
 * Selects the existing Epic or Oracle projection for the configured FHIR
 * destination. Unsupported destinations return the v1 contract without a FHIR
 * read. Laboratory pages keep their own Oracle provider.
 */
@Component
public class ConfiguredDestinationModelBoundary implements ConfiguredModelBoundarySource {

    private final FhirServersProperties servers;
    private final EpicSandboxClinicalProjectionService epicProjection;
    private final EpicIntegrationProfile epicProfile;
    private final OracleSandboxModelBoundaryService oracleModelBoundary;
    private final OracleHealthIntegrationProfile oracleProfile;

    public ConfiguredDestinationModelBoundary(
            FhirServersProperties servers,
            EpicSandboxClinicalProjectionService epicProjection,
            EpicIntegrationProfile epicProfile,
            OracleSandboxModelBoundaryService oracleModelBoundary,
            OracleHealthIntegrationProfile oracleProfile) {
        if (servers == null) {
            throw new IllegalArgumentException("FHIR server properties must be provided");
        }
        if (epicProjection == null) {
            throw new IllegalArgumentException("Epic sandbox clinical projection service must be provided");
        }
        if (epicProfile == null) {
            throw new IllegalArgumentException("Epic integration profile must be provided");
        }
        if (oracleModelBoundary == null) {
            throw new IllegalArgumentException("Oracle sandbox model boundary service must be provided");
        }
        if (oracleProfile == null) {
            throw new IllegalArgumentException("Oracle Health integration profile must be provided");
        }
        this.servers = servers;
        this.epicProjection = epicProjection;
        this.epicProfile = epicProfile;
        this.oracleModelBoundary = oracleModelBoundary;
        this.oracleProfile = oracleProfile;
    }

    @Override
    public ModelBoundaryContract currentContract() {
        String destination = servers.activeServer() == null ? "" : servers.activeServer().trim();
        if (EpicIntegrationProfile.SANDBOX_SERVER.equals(destination)) {
            return ModelBoundaryMapper.from(epicProjection.assemble(epicProfile));
        }
        if (OracleHealthIntegrationProfile.SANDBOX_SERVER.equals(destination)) {
            return oracleModelBoundary.assemble(oracleProfile);
        }
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                destination,
                null,
                null,
                ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE,
                null,
                null,
                null,
                null,
                null);
    }
}
