package lab.healthcare.fhir.smart;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.FhirAuthenticationSettings;
import lab.healthcare.fhir.auth.oauth2.OAuth2TokenException;
import lab.healthcare.fhir.auth.oauth2.OAuth2TokenResponseParser;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.net.URI;
import java.net.URLDecoder;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;

public class AuthorizationCodeClient {

    private final HttpClient httpClient;
    private final OAuth2TokenResponseParser parser;

    public AuthorizationCodeClient() {
        this(
                HttpClient.newBuilder()
                        .connectTimeout(Duration.ofSeconds(5))
                        .followRedirects(HttpClient.Redirect.NEVER)
                        .build(),
                Clock.systemUTC());
    }

    AuthorizationCodeClient(HttpClient httpClient, Clock clock) {
        this.httpClient = httpClient;
        this.parser = new OAuth2TokenResponseParser(new ObjectMapper(), clock);
    }

    public AuthorizationSession createAuthorization(
            FhirAuthenticationSettings authentication,
            SmartConfiguration configuration) {
        requireSmart(authentication);
        if (configuration == null
                || configuration.authorizationEndpoint() == null
                || configuration.authorizationEndpoint().isBlank()) {
            throw new IllegalArgumentException("SMART authorization_endpoint must be provided");
        }
        String verifier = Pkce.codeVerifier();
        String challenge = Pkce.codeChallengeS256(verifier);
        String state = Pkce.newState();
        String url = configuration.authorizationEndpoint()
                + "?"
                + query(
                        "response_type", "code",
                        "client_id", authentication.clientId(),
                        "redirect_uri", authentication.redirectUri(),
                        "scope", authentication.scope(),
                        "state", state,
                        "aud", authentication.aud(),
                        "code_challenge", challenge,
                        "code_challenge_method", "S256");
        return new AuthorizationSession(url, state, verifier, challenge);
    }

    public String authorizationCodeFromRedirect(String redirectLocation, String expectedState) {
        if (redirectLocation == null || redirectLocation.isBlank()) {
            throw new OAuth2TokenException("OAuth authorization failed: missing redirect");
        }
        if (expectedState == null || expectedState.isBlank()) {
            throw new IllegalArgumentException("OAuth state must be provided");
        }
        Map<String, String> params = queryParams(redirectLocation);
        String actualState = params.get("state");
        if (!expectedState.equals(actualState)) {
            throw new OAuth2TokenException("OAuth authorization failed: invalid state");
        }
        String code = params.get("code");
        if (code == null || code.isBlank()) {
            throw new OAuth2TokenException("OAuth authorization failed: missing authorization code");
        }
        return code;
    }

    public AccessToken exchangeAuthorizationCode(
            FhirAuthenticationSettings authentication,
            String tokenEndpoint,
            String code,
            String codeVerifier) {
        requireSmart(authentication);
        requireText(tokenEndpoint, "token endpoint");
        requireText(code, "authorization code");
        requireText(codeVerifier, "PKCE code_verifier");
        String form = query(
                "grant_type", "authorization_code",
                "code", code,
                "redirect_uri", authentication.redirectUri(),
                "client_id", authentication.clientId(),
                "code_verifier", codeVerifier);
        return postToken(tokenEndpoint, form);
    }

    public AccessToken refreshAccessToken(
            FhirAuthenticationSettings authentication,
            String tokenEndpoint,
            String refreshToken) {
        requireSmart(authentication);
        requireText(tokenEndpoint, "token endpoint");
        requireText(refreshToken, "refresh token");
        String form = query(
                "grant_type", "refresh_token",
                "refresh_token", refreshToken,
                "client_id", authentication.clientId());
        return postToken(tokenEndpoint, form);
    }

    public AccessToken authorizeSynthetically(
            FhirAuthenticationSettings authentication,
            SmartConfiguration configuration) {
        AuthorizationSession session = createAuthorization(authentication, configuration);
        HttpRequest request = HttpRequest.newBuilder(URI.create(session.authorizationUrl()))
                .timeout(Duration.ofSeconds(10))
                .GET()
                .build();
        try {
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() != 302) {
                throw new OAuth2TokenException(
                        "OAuth authorization failed: HTTP " + response.statusCode());
            }
            String location = response.headers().firstValue("location").orElse("");
            String code = authorizationCodeFromRedirect(location, session.state());
            return exchangeAuthorizationCode(
                    authentication, configuration.tokenEndpoint(), code, session.codeVerifier());
        } catch (OAuth2TokenException ex) {
            throw ex;
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new OAuth2TokenException("OAuth authorization endpoint unavailable", ex);
        } catch (Exception ex) {
            throw new OAuth2TokenException("OAuth authorization endpoint unavailable", ex);
        }
    }

    AccessToken parseTokenResponse(int statusCode, String body) {
        return parser.parse(statusCode, body);
    }

    private AccessToken postToken(String tokenEndpoint, String form) {
        HttpRequest request = HttpRequest.newBuilder(URI.create(tokenEndpoint))
                .timeout(Duration.ofSeconds(10))
                .header("Accept", "application/json")
                .header("Content-Type", "application/x-www-form-urlencoded")
                .POST(HttpRequest.BodyPublishers.ofString(form))
                .build();
        try {
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            return parser.parse(response.statusCode(), response.body());
        } catch (OAuth2TokenException ex) {
            throw ex;
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new OAuth2TokenException("OAuth token endpoint unavailable", ex);
        } catch (Exception ex) {
            throw new OAuth2TokenException("OAuth token endpoint unavailable", ex);
        }
    }

    private static void requireSmart(FhirAuthenticationSettings authentication) {
        if (authentication == null || !authentication.isSmartAuthorizationCode()) {
            throw new IllegalArgumentException("SMART authorization code settings must be provided");
        }
    }

    private static void requireText(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " must be provided");
        }
    }

    private static String query(String... keysAndValues) {
        if (keysAndValues.length % 2 != 0) {
            throw new IllegalArgumentException("Query parameters must be name/value pairs");
        }
        StringBuilder builder = new StringBuilder();
        for (int index = 0; index < keysAndValues.length; index += 2) {
            if (index > 0) {
                builder.append('&');
            }
            builder.append(encode(keysAndValues[index]))
                    .append('=')
                    .append(encode(keysAndValues[index + 1]));
        }
        return builder.toString();
    }

    private static Map<String, String> queryParams(String location) {
        URI uri = URI.create(location);
        String rawQuery = uri.getRawQuery();
        Map<String, String> params = new LinkedHashMap<>();
        if (rawQuery == null || rawQuery.isBlank()) {
            return params;
        }
        for (String pair : rawQuery.split("&")) {
            int separator = pair.indexOf('=');
            if (separator < 0) {
                params.put(decode(pair), "");
            } else {
                params.put(decode(pair.substring(0, separator)), decode(pair.substring(separator + 1)));
            }
        }
        return params;
    }

    private static String encode(String value) {
        return URLEncoder.encode(value == null ? "" : value, StandardCharsets.UTF_8).replace("+", "%20");
    }

    private static String decode(String value) {
        return URLDecoder.decode(value, StandardCharsets.UTF_8);
    }
}
