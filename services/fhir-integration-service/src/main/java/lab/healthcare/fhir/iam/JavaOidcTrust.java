package lab.healthcare.fhir.iam;

import com.fasterxml.jackson.annotation.JsonAutoDetect;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.MapperFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.json.JsonMapper;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.List;
import java.util.regex.Pattern;

/** Explicit immutable operator registration; never selected by a token or a request. */
record JavaOidcTrust(String contractVersion, String providerId, boolean enabled, String issuer,
        String discoveryUrl, String expectedJwksUri, List<String> endpointAllowlist,
        String audience, String algorithm, String accessTokenProfile, boolean allowHttpLoopback,
        List<String> allowedOrganizationIds, int clockSkewSeconds, int maxAccessTokenLifetimeSeconds,
        int jwksRefreshSeconds, int jwksHardTtlSeconds, int unknownKidRefreshMinIntervalSeconds,
        int httpTimeoutMillis, int metadataMaxBytes, List<Binding> bindings) {
    static final String AUDIENCE = "healthcare-interop-api";
    static final String PERMISSION = "iam.java-workload-context.read";
    static final String ROUTE = "/iam-lab/v1/workload-context";
    static final Pattern ID = Pattern.compile("[A-Za-z0-9][A-Za-z0-9.-]{0,63}");
    static final ObjectMapper JSON = JsonMapper.builder()
            .enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION)
            .disable(MapperFeature.ALLOW_COERCION_OF_SCALARS)
            .disable(DeserializationFeature.ACCEPT_FLOAT_AS_INT)
            .enable(DeserializationFeature.FAIL_ON_NULL_FOR_PRIMITIVES)
            .enable(DeserializationFeature.FAIL_ON_MISSING_CREATOR_PROPERTIES)
            .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS)
            .propertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE).build();

    record Binding(String clientId, String externalSubject, String internalPrincipalId,
            String principalType, boolean bindingEnabled, boolean principalEnabled,
            String organizationId, boolean membershipEnabled, String audience, List<String> permissions) {
        Binding {
            require(clientId != null && clientId.matches("[A-Za-z0-9._-]{1,128}"));
            require(externalSubject != null && externalSubject.length() <= 512 && !externalSubject.isEmpty()
                    && externalSubject.chars().noneMatch(c -> c < 33));
            require(id(internalPrincipalId) && id(organizationId) && "workload".equals(principalType));
            require(AUDIENCE.equals(audience) && permissions != null && permissions.size() <= 16);
            require(new HashSet<>(permissions).size() == permissions.size()
                    && permissions.stream().allMatch(p -> p != null && p.matches("[a-z][a-z0-9.-]{0,79}")));
            permissions = List.copyOf(permissions);
        }
        @Override public String toString() { return "Binding[redacted]"; }
    }

    JavaOidcTrust {
        require("java-oidc-workload-v1".equals(contractVersion) && id(providerId));
        require(AUDIENCE.equals(audience) && "RS256".equals(algorithm)
                && "keycloak-client-credentials-v1".equals(accessTokenProfile));
        require(endpointAllowlist != null && endpointAllowlist.size() <= 9);
        require(allowedOrganizationIds != null && !allowedOrganizationIds.isEmpty()
                && allowedOrganizationIds.size() <= 32 && allowedOrganizationIds.stream().allMatch(JavaOidcTrust::id)
                && new HashSet<>(allowedOrganizationIds).size() == allowedOrganizationIds.size());
        require(clockSkewSeconds >= 0 && clockSkewSeconds <= 60
                && maxAccessTokenLifetimeSeconds > 0 && maxAccessTokenLifetimeSeconds <= 300
                && jwksRefreshSeconds >= 30 && jwksRefreshSeconds <= 300
                && jwksHardTtlSeconds >= jwksRefreshSeconds && jwksHardTtlSeconds <= 900
                && unknownKidRefreshMinIntervalSeconds >= 30 && unknownKidRefreshMinIntervalSeconds <= 300
                && httpTimeoutMillis > 0 && httpTimeoutMillis <= 2000
                && metadataMaxBytes >= 1024 && metadataMaxBytes <= 1048576);
        require(bindings != null && bindings.size() <= 64);
        require(bindings.stream().map(Binding::clientId).distinct().count() == bindings.size()
                && bindings.stream().map(Binding::externalSubject).distinct().count() == bindings.size());
        for (String url : List.of(issuer, discoveryUrl, expectedJwksUri)) { url(url, allowHttpLoopback); }
        endpointAllowlist.forEach(u -> url(u, allowHttpLoopback));
        require(endpointAllowlist.contains(discoveryUrl) && endpointAllowlist.contains(expectedJwksUri));
        endpointAllowlist = List.copyOf(endpointAllowlist);
        allowedOrganizationIds = List.copyOf(allowedOrganizationIds);
        bindings = List.copyOf(bindings);
    }

    static boolean id(String s) { return s != null && ID.matcher(s).matches(); }
    static void require(boolean condition) {
        if (!condition) { throw new JavaOidcFailure("configuration_incomplete", 503); }
    }
    private static void url(String value, boolean local) {
        require(value != null && value.length() <= 2048 && value.chars().noneMatch(c -> c < 33));
        URI uri = URI.create(value);
        String host = uri.getHost();
        require(host != null && uri.getUserInfo() == null && uri.getRawQuery() == null && uri.getFragment() == null);
        boolean loopback = List.of("localhost", "127.0.0.1", "[::1]", "::1").contains(host);
        require(("https".equals(uri.getScheme()) && (!loopback || local))
                || ("http".equals(uri.getScheme()) && loopback && local));
        // Literal IP endpoints are deliberately narrower than corporate DNS trust: loopback lab only.
        require(loopback || !(host.matches("[0-9.]+") || host.contains(":")));
        require(uri.getPort() == -1 || (uri.getPort() >= 1024 && uri.getPort() <= 65535)
                || ("https".equals(uri.getScheme()) && uri.getPort() == 443));
    }
    static JavaOidcTrust load(String path) {
        try (var stream = Files.newInputStream(Path.of(path))) {
            byte[] bytes = stream.readNBytes(65537);
            require(bytes.length <= 65536);
            return JSON.readValue(bytes, JavaOidcTrust.class);
        } catch (Exception failure) {
            throw new JavaOidcFailure("configuration_incomplete", 503);
        }
    }
    @Override public String toString() { return "JavaOidcTrust[redacted]"; }
}
