package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.connectivity.FhirConnectivityStatus;
import lab.healthcare.fhir.connectivity.FhirEndpointConnectivityVerifier;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.server.FhirDeploymentEnvironment;

import org.springframework.stereotype.Component;

/**
 * Inspects Oracle sandbox connection readiness and optionally probes metadata.
 * Invalid configuration never reaches the HTTP probe.
 */
@Component
public class OracleSandboxReadinessService {

    private final OracleSandboxProfileValidator validator;
    private final FhirEndpointConnectivityVerifier verifier;

    public OracleSandboxReadinessService(
            OracleSandboxProfileValidator validator, FhirEndpointConnectivityVerifier verifier) {
        if (validator == null) {
            throw new IllegalArgumentException("Oracle sandbox profile validator must be provided");
        }
        if (verifier == null) {
            throw new IllegalArgumentException("FHIR endpoint connectivity verifier must be provided");
        }
        this.validator = validator;
        this.verifier = verifier;
    }

    public OracleSandboxReadiness inspect(OracleHealthIntegrationProfile profile) {
        if (profile == null) {
            return new OracleSandboxReadiness(
                    OracleSandboxReadinessState.NOT_CONFIGURED,
                    OracleHealthIntegrationProfile.SANDBOX_SERVER,
                    false,
                    FhirDeploymentEnvironment.SANDBOX,
                    null,
                    "Oracle Health integration profile is missing");
        }
        OracleSandboxConfiguration configuration = OracleSandboxConfiguration.from(profile);
        if (!profile.enabled()) {
            return OracleSandboxReadiness.disabled(profile.serverProfileName());
        }
        if (profile.environment() == OracleHealthEnvironment.PRODUCTION) {
            try {
                validator.validateDisabledAllowed(profile);
                return new OracleSandboxReadiness(
                        OracleSandboxReadinessState.CONFIGURED,
                        profile.serverProfileName(),
                        true,
                        FhirDeploymentEnvironment.PRODUCTION,
                        null,
                        "Oracle Health PRODUCTION is represented but not in sandbox connectivity scope");
            } catch (OracleHealthProfileException ex) {
                return new OracleSandboxReadiness(
                        OracleSandboxReadinessState.INVALID_CONFIGURATION,
                        profile.serverProfileName(),
                        true,
                        FhirDeploymentEnvironment.PRODUCTION,
                        FhirErrorCategory.VALIDATION_ERROR,
                        ex.getMessage());
            }
        }
        try {
            validator.validateForConnectivity(profile);
            return new OracleSandboxReadiness(
                    OracleSandboxReadinessState.READY_FOR_CONNECTIVITY_CHECK,
                    profile.serverProfileName(),
                    true,
                    configuration.deploymentEnvironment(),
                    null,
                    "Oracle Health sandbox is configured for a connectivity check");
        } catch (OracleHealthProfileException ex) {
            return new OracleSandboxReadiness(
                    OracleSandboxReadinessState.INVALID_CONFIGURATION,
                    profile.serverProfileName(),
                    true,
                    configuration.deploymentEnvironment(),
                    FhirErrorCategory.VALIDATION_ERROR,
                    ex.getMessage());
        }
    }

    public FhirConnectivityStatus checkConnectivity(OracleHealthIntegrationProfile profile) {
        OracleSandboxReadiness readiness = inspect(profile);
        if (readiness.state() == OracleSandboxReadinessState.DISABLED
                || readiness.state() == OracleSandboxReadinessState.NOT_CONFIGURED) {
            return FhirConnectivityStatus.skipped();
        }
        if (readiness.state() == OracleSandboxReadinessState.CONFIGURED) {
            return FhirConnectivityStatus.skipped();
        }
        if (readiness.state() == OracleSandboxReadinessState.INVALID_CONFIGURATION) {
            throw new OracleHealthProfileException(readiness.detail());
        }
        validator.validateForConnectivity(profile);
        return verifier.verify(profile.fhirBaseUrl());
    }
}
