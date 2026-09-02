package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.AccessTokenProvider;
import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.server.FhirDeploymentEnvironment;
import lab.healthcare.fhir.smart.SmartAuthorizationCoordinator;
import lab.healthcare.fhir.smart.SmartAuthorizationException;
import lab.healthcare.fhir.smart.SmartAuthorizationStart;
import lab.healthcare.fhir.smart.SmartConfiguration;
import lab.healthcare.fhir.smart.SmartConfigurationClient;
import lab.healthcare.fhir.smart.SmartTokenExchangeResult;

import org.springframework.stereotype.Component;

/**
 * Oracle Health sandbox SMART authorization orchestrator. Discovers generic SMART
 * metadata and starts an interactive Authorization Code + PKCE flow. Does not
 * read Patient and does not invent Oracle hosts.
 */
@Component
public class OracleSandboxAuthenticationService {

    private final OracleSandboxProfileValidator validator;
    private final SmartConfigurationClient smartConfigurationClient;
    private final SmartAuthorizationCoordinator coordinator;
    private volatile IssuedAccessTokenProvider issued;

    public OracleSandboxAuthenticationService(
            OracleSandboxProfileValidator validator,
            SmartConfigurationClient smartConfigurationClient,
            SmartAuthorizationCoordinator coordinator) {
        if (validator == null) {
            throw new IllegalArgumentException("Oracle sandbox profile validator must be provided");
        }
        if (smartConfigurationClient == null) {
            throw new IllegalArgumentException("SMART configuration client must be provided");
        }
        if (coordinator == null) {
            throw new IllegalArgumentException("SMART authorization coordinator must be provided");
        }
        this.validator = validator;
        this.smartConfigurationClient = smartConfigurationClient;
        this.coordinator = coordinator;
    }

    public OracleSandboxAuthReadiness inspect(OracleHealthIntegrationProfile profile) {
        if (profile == null) {
            return new OracleSandboxAuthReadiness(
                    OracleSandboxAuthReadinessState.NOT_CONFIGURED,
                    OracleHealthIntegrationProfile.SANDBOX_SERVER,
                    false,
                    FhirDeploymentEnvironment.SANDBOX,
                    null,
                    "Oracle Health integration profile is missing");
        }
        if (!profile.enabled()) {
            return OracleSandboxAuthReadiness.disabled(profile.serverProfileName());
        }
        if (profile.environment() == OracleHealthEnvironment.PRODUCTION) {
            try {
                validator.validateDisabledAllowed(profile);
                return new OracleSandboxAuthReadiness(
                        OracleSandboxAuthReadinessState.CONFIGURED,
                        profile.serverProfileName(),
                        true,
                        FhirDeploymentEnvironment.PRODUCTION,
                        null,
                        "Oracle Health PRODUCTION is represented but not in sandbox authorization scope");
            } catch (OracleHealthProfileException ex) {
                return invalid(profile, FhirDeploymentEnvironment.PRODUCTION, ex.getMessage());
            }
        }
        try {
            validator.validateForAuthorization(profile);
            return new OracleSandboxAuthReadiness(
                    OracleSandboxAuthReadinessState.READY_FOR_AUTHORIZATION,
                    profile.serverProfileName(),
                    true,
                    FhirDeploymentEnvironment.SANDBOX,
                    null,
                    "Oracle Health sandbox is configured for SMART authorization");
        } catch (OracleHealthProfileException ex) {
            return invalid(profile, FhirDeploymentEnvironment.SANDBOX, ex.getMessage());
        }
    }

    public SmartAuthorizationStart startAuthorization(OracleHealthIntegrationProfile profile) {
        OracleSandboxAuthReadiness readiness = inspect(profile);
        if (readiness.state() == OracleSandboxAuthReadinessState.DISABLED
                || readiness.state() == OracleSandboxAuthReadinessState.NOT_CONFIGURED) {
            throw new OracleHealthProfileException("Oracle Health sandbox profile is disabled");
        }
        if (readiness.state() == OracleSandboxAuthReadinessState.CONFIGURED) {
            throw new OracleHealthProfileException(
                    "Oracle Health authorization is only supported for SANDBOX");
        }
        if (readiness.state() == OracleSandboxAuthReadinessState.INVALID_CONFIGURATION) {
            throw new OracleHealthProfileException(readiness.detail());
        }
        validator.validateForAuthorization(profile);
        SmartConfiguration configuration = smartConfigurationClient.fetch(profile.smartConfigurationUrl());
        return coordinator.start(profile.toAuthenticationSettings(), configuration, profile.serverProfileName());
    }

    public AccessToken completeAuthorization(String redirectLocation) {
        SmartTokenExchangeResult result = completeAuthorizationDiagnosed(redirectLocation);
        if (!result.succeeded()) {
            throw new SmartAuthorizationException(result.diagnosis().detail());
        }
        return result.token();
    }

    public SmartTokenExchangeResult completeAuthorizationDiagnosed(String redirectLocation) {
        SmartTokenExchangeResult result = coordinator.completeDiagnosed(redirectLocation);
        if (result.succeeded()) {
            this.issued = result.asProvider();
        }
        return result;
    }

    public AccessTokenProvider issuedTokenProvider() {
        if (issued == null) {
            throw new SmartAuthorizationException("SMART authorization failed: no issued access token");
        }
        return issued;
    }

    private static OracleSandboxAuthReadiness invalid(
            OracleHealthIntegrationProfile profile, FhirDeploymentEnvironment environment, String detail) {
        return new OracleSandboxAuthReadiness(
                OracleSandboxAuthReadinessState.INVALID_CONFIGURATION,
                profile.serverProfileName(),
                true,
                environment,
                FhirErrorCategory.VALIDATION_ERROR,
                detail);
    }
}
