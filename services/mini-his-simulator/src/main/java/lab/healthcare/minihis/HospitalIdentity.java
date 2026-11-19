package lab.healthcare.minihis;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.io.InputStream;
import java.time.Instant;
import java.net.URL;
import java.util.Collection;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

final class HospitalBindings {
    record Binding(String organization, String role) {
    }

    private static final ObjectMapper JSON = new ObjectMapper();

    private HospitalBindings() {
    }

    static Map<String, Binding> load(InputStream input) throws IOException {
        JsonNode root = JSON.readTree(input);
        Map<String, Binding> bindings = new LinkedHashMap<>();
        if (root == null || !root.isObject()) {
            return bindings;
        }
        root.fields().forEachRemaining(entry -> {
            JsonNode value = entry.getValue();
            String organization = value.path("organization").asText("");
            String role = value.path("role").asText("");
            if (entry.getKey().matches("[a-z0-9][a-z0-9.]{0,63}") && organization.startsWith("org-") && !role.isBlank()) {
                bindings.put(entry.getKey(), new Binding(organization, role));
            }
        });
        return Map.copyOf(bindings);
    }
}

final class HospitalIdentity {
    static final Set<String> HIS_ROLES = Set.of("clinician", "clinical-reviewer", "auditor", "operator");

    private HospitalIdentity() {
    }

    static WardPrincipal accept(
            Map<String, Object> claims, Map<String, HospitalBindings.Binding> bindings,
            String issuer, String audience, Instant now) throws HospitalRejection {
        if (claims == null || !issuer.equals(issuerOf(claims.get("iss"))) || !audienceMatches(claims.get("aud"), audience)) {
            throw new HospitalRejection("invalid_token", 401);
        }
        Instant expires = expiry(claims.get("exp"));
        if (expires == null || !expires.isAfter(now)) {
            throw new HospitalRejection("invalid_token", 401);
        }
        Object username = claims.get("preferred_username");
        HospitalBindings.Binding binding = username instanceof String name ? bindings.get(name) : null;
        if (binding == null || !binding.organization().equals(claims.get("organization"))) {
            throw new HospitalRejection("organization_denied", 403);
        }
        if (!HIS_ROLES.contains(binding.role()) || !roles(claims).contains(binding.role())) {
            throw new HospitalRejection("role_denied", 403);
        }
        return new WardPrincipal(username.toString(), binding.role(), binding.organization(), "oidc");
    }

    private static String issuerOf(Object issuer) {
        if (issuer instanceof URL url) {
            return url.toExternalForm();
        }
        return issuer == null ? "" : issuer.toString();
    }

    private static boolean audienceMatches(Object audience, String expected) {
        if (audience instanceof String value) {
            return expected.equals(value);
        }
        return audience instanceof Collection<?> values && values.contains(expected);
    }

    private static Instant expiry(Object value) {
        if (value instanceof Instant instant) {
            return instant;
        }
        if (value instanceof Date date) {
            return date.toInstant();
        }
        if (value instanceof Number number) {
            return Instant.ofEpochSecond(number.longValue());
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private static List<String> roles(Map<String, Object> claims) {
        Object access = claims.get("realm_access");
        if (!(access instanceof Map<?, ?> map) || !(map.get("roles") instanceof Collection<?> values)) {
            return List.of();
        }
        return values.stream().map(String::valueOf).toList();
    }
}
