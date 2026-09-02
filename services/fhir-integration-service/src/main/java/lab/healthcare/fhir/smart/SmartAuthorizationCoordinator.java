package lab.healthcare.fhir.smart;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.FhirAuthenticationType;
import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.auth.oauth2.OAuth2TokenException;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;

/**
 * Interactive Authorization Code + PKCE: generate a URL, store the verifier,
 * then exchange after callback {@code state} validation. Not part of the FHIR
 * resilience pipeline.
 */
@Component
public class SmartAuthorizationCoordinator {

    static final Duration SESSION_TTL = Duration.ofMinutes(10);

    private final AuthorizationSessionStore store;
    private final AuthorizationCodeClient authorizationCodeClient;
    private final Clock clock;

    @Autowired
    public SmartAuthorizationCoordinator(
            AuthorizationSessionStore store, AuthorizationCodeClient authorizationCodeClient) {
        this(store, authorizationCodeClient, Clock.systemUTC());
    }

    public SmartAuthorizationCoordinator(
            AuthorizationSessionStore store, AuthorizationCodeClient authorizationCodeClient, Clock clock) {
        if (store == null) {
            throw new IllegalArgumentException("authorization session store must be provided");
        }
        if (authorizationCodeClient == null) {
            throw new IllegalArgumentException("authorization code client must be provided");
        }
        this.store = store;
        this.authorizationCodeClient = authorizationCodeClient;
        this.clock = clock == null ? Clock.systemUTC() : clock;
    }

    public SmartAuthorizationStart start(
            FhirAuthenticationSettings authentication,
            SmartConfiguration configuration,
            String destination) {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("authorization destination must be provided");
        }
        AuthorizationSession session = authorizationCodeClient.createAuthorization(authentication, configuration);
        Instant expiresAt = Instant.now(clock).plus(SESSION_TTL);
        store.save(new PendingAuthorizationSession(
                destination.trim(),
                session.state(),
                session.codeVerifier(),
                session.codeChallenge(),
                session.authorizationUrl(),
                configuration.tokenEndpoint(),
                authentication.clientId(),
                authentication.redirectUri(),
                expiresAt,
                configuration.tokenEndpointAuthMethodsSupported()));
        return new SmartAuthorizationStart(
                destination.trim(),
                session.authorizationUrl(),
                session.state(),
                expiresAt,
                configuration.tokenEndpointAuthMethodsSupported());
    }

    public AccessToken complete(String redirectLocation) {
        SmartTokenExchangeResult result = completeDiagnosed(redirectLocation);
        if (!result.succeeded()) {
            throw new SmartAuthorizationException(result.diagnosis().detail());
        }
        return result.token();
    }

    public SmartTokenExchangeResult completeDiagnosed(String redirectLocation) {
        SmartAuthorizationCallback callback = SmartAuthorizationCallback.parse(redirectLocation);
        if (callback.state() == null) {
            throw new SmartAuthorizationException("SMART authorization failed: missing state");
        }
        PendingAuthorizationSession session = store.consume(callback.state());
        if (!session.state().equals(callback.state())) {
            throw new SmartAuthorizationException("SMART authorization failed: invalid state");
        }
        if (callback.hasOAuthError()) {
            return new SmartTokenExchangeResult(
                    null,
                    SmartTokenExchangeDiagnoser.fromAuthorizationFailure(
                            callback.error(),
                            callback.errorDescription(),
                            session.tokenEndpointAuthMethodsSupported()));
        }
        if (callback.code() == null) {
            throw new SmartAuthorizationException("SMART authorization failed: missing authorization code");
        }
        FhirAuthenticationSettings authentication = new FhirAuthenticationSettings(
                FhirAuthenticationType.SMART_AUTHORIZATION_CODE,
                null,
                session.clientId(),
                "",
                null,
                session.redirectUri(),
                "",
                null);
        try {
            AccessToken token = authorizationCodeClient.exchangeAuthorizationCode(
                    authentication, session.tokenEndpoint(), callback.code(), session.codeVerifier());
            return new SmartTokenExchangeResult(
                    token, SmartTokenExchangeDiagnosis.issued(session.tokenEndpointAuthMethodsSupported()));
        } catch (OAuth2TokenException ex) {
            return new SmartTokenExchangeResult(
                    null,
                    SmartTokenExchangeDiagnoser.fromTokenFailure(
                            ex, session.tokenEndpointAuthMethodsSupported()));
        }
    }

    public IssuedAccessTokenProvider completeAsProvider(String redirectLocation) {
        return new IssuedAccessTokenProvider(complete(redirectLocation));
    }
}
