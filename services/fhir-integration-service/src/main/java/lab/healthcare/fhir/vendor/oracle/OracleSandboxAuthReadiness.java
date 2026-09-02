package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.server.FhirDeploymentEnvironment;

/**
 * Inspectable Oracle sandbox SMART authentication readiness. Safe to log: no secrets.
 */
public record OracleSandboxAuthReadiness(
        OracleSandboxAuthReadinessState state,
        String destination,
        boolean enabled,
        FhirDeploymentEnvironment deploymentEnvironment,
        FhirErrorCategory error,
        String detail) {

    public OracleSandboxAuthReadiness {
        if (state == null) {
            throw new IllegalArgumentException("Oracle sandbox auth readiness state must be provided");
        }
        destination = destination == null || destination.isBlank()
                ? OracleHealthIntegrationProfile.SANDBOX_SERVER
                : destination.trim();
        if (deploymentEnvironment == null) {
            deploymentEnvironment = FhirDeploymentEnvironment.SANDBOX;
        }
        detail = OracleHealthProfileException.requireSafe(
                detail == null || detail.isBlank() ? state.name() : detail.trim());
        if (state == OracleSandboxAuthReadinessState.INVALID_CONFIGURATION && error == null) {
            error = FhirErrorCategory.VALIDATION_ERROR;
        }
        if (state != OracleSandboxAuthReadinessState.INVALID_CONFIGURATION) {
            error = null;
        }
    }

    public static OracleSandboxAuthReadiness disabled(String destination) {
        return new OracleSandboxAuthReadiness(
                OracleSandboxAuthReadinessState.DISABLED,
                destination,
                false,
                FhirDeploymentEnvironment.SANDBOX,
                null,
                "Oracle Health sandbox profile is disabled");
    }

    @Override
    public String toString() {
        return "OracleSandboxAuthReadiness[state="
                + state
                + ", destination="
                + destination
                + ", enabled="
                + enabled
                + ", deploymentEnvironment="
                + deploymentEnvironment
                + ", error="
                + error
                + ", detail="
                + detail
                + "]";
    }
}
