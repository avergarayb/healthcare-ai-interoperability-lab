package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.server.FhirDeploymentEnvironment;

/**
 * Inspectable Epic sandbox SMART authentication readiness. Safe to log: no secrets.
 */
public record EpicSandboxAuthReadiness(
        EpicSandboxAuthReadinessState state,
        String destination,
        boolean enabled,
        FhirDeploymentEnvironment deploymentEnvironment,
        FhirErrorCategory error,
        String detail) {

    public EpicSandboxAuthReadiness {
        if (state == null) {
            throw new IllegalArgumentException("Epic sandbox auth readiness state must be provided");
        }
        destination = destination == null || destination.isBlank()
                ? EpicIntegrationProfile.SANDBOX_SERVER
                : destination.trim();
        if (deploymentEnvironment == null) {
            deploymentEnvironment = FhirDeploymentEnvironment.SANDBOX;
        }
        detail = EpicProfileException.requireSafe(
                detail == null || detail.isBlank() ? state.name() : detail.trim());
        if (state == EpicSandboxAuthReadinessState.INVALID_CONFIGURATION && error == null) {
            error = FhirErrorCategory.VALIDATION_ERROR;
        }
        if (state != EpicSandboxAuthReadinessState.INVALID_CONFIGURATION) {
            error = null;
        }
    }

    public static EpicSandboxAuthReadiness disabled(String destination) {
        return new EpicSandboxAuthReadiness(
                EpicSandboxAuthReadinessState.DISABLED,
                destination,
                false,
                FhirDeploymentEnvironment.SANDBOX,
                null,
                "Epic sandbox profile is disabled");
    }

    @Override
    public String toString() {
        return "EpicSandboxAuthReadiness[state="
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
