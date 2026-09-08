package lab.healthcare.fhir.vendor.epic;

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

import java.util.Optional;

/**
 * Epic sandbox SMART authorization orchestrator. Discovers generic SMART
 * metadata and starts an interactive Authorization Code + PKCE flow. Does not
 * read Patient and does not invent Epic hosts.
 */
@Component
public class EpicSandboxAuthenticationService {

    private final EpicProfileValidator validator;
    private final SmartConfigurationClient smartConfigurationClient;
    private final SmartAuthorizationCoordinator coordinator;
    private volatile IssuedAccessTokenProvider issued;

    public EpicSandboxAuthenticationService(
            EpicProfileValidator validator,
            SmartConfigurationClient smartConfigurationClient,
            SmartAuthorizationCoordinator coordinator) {
        if (validator == null) {
            throw new IllegalArgumentException("Epic profile validator must be provided");
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

    public EpicSandboxAuthReadiness inspect(EpicIntegrationProfile profile) {
        if (profile == null) {
            return new EpicSandboxAuthReadiness(
                    EpicSandboxAuthReadinessState.NOT_CONFIGURED,
                    EpicIntegrationProfile.SANDBOX_SERVER,
                    false,
                    FhirDeploymentEnvironment.SANDBOX,
                    null,
                    "Epic integration profile is missing");
        }
        if (!profile.enabled()) {
            return EpicSandboxAuthReadiness.disabled(profile.serverProfileName());
        }
        if (profile.environment() == EpicEnvironment.PRODUCTION) {
            try {
                validator.validate(profile);
                return new EpicSandboxAuthReadiness(
                        EpicSandboxAuthReadinessState.CONFIGURED,
                        profile.serverProfileName(),
                        true,
                        FhirDeploymentEnvironment.PRODUCTION,
                        null,
                        "Epic PRODUCTION is represented but not in sandbox authorization scope");
            } catch (EpicProfileException ex) {
                return invalid(profile, FhirDeploymentEnvironment.PRODUCTION, ex.getMessage());
            }
        }
        try {
            validator.validateForAuthorization(profile);
            return new EpicSandboxAuthReadiness(
                    EpicSandboxAuthReadinessState.READY_FOR_AUTHORIZATION,
                    profile.serverProfileName(),
                    true,
                    FhirDeploymentEnvironment.SANDBOX,
                    null,
                    "Epic sandbox is configured for SMART authorization");
        } catch (EpicProfileException ex) {
            return invalid(profile, FhirDeploymentEnvironment.SANDBOX, ex.getMessage());
        }
    }

    public SmartAuthorizationStart startAuthorization(EpicIntegrationProfile profile) {
        EpicSandboxAuthReadiness readiness = inspect(profile);
        if (readiness.state() == EpicSandboxAuthReadinessState.DISABLED
                || readiness.state() == EpicSandboxAuthReadinessState.NOT_CONFIGURED) {
            throw new EpicProfileException("Epic sandbox profile is disabled");
        }
        if (readiness.state() == EpicSandboxAuthReadinessState.CONFIGURED) {
            throw new EpicProfileException("Epic authorization is only supported for SANDBOX");
        }
        if (readiness.state() == EpicSandboxAuthReadinessState.INVALID_CONFIGURATION) {
            throw new EpicProfileException(readiness.detail());
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
        return issuedProviderIfPresent()
                .orElseThrow(() -> new SmartAuthorizationException(
                        "SMART authorization failed: no issued access token"));
    }

    public Optional<IssuedAccessTokenProvider> issuedProviderIfPresent() {
        if (issued != null) {
            return Optional.of(issued);
        }
        return coordinator.lastIssuedProvider();
    }

    private static EpicSandboxAuthReadiness invalid(
            EpicIntegrationProfile profile, FhirDeploymentEnvironment environment, String detail) {
        return new EpicSandboxAuthReadiness(
                EpicSandboxAuthReadinessState.INVALID_CONFIGURATION,
                profile.serverProfileName(),
                true,
                environment,
                FhirErrorCategory.VALIDATION_ERROR,
                detail);
    }
}
