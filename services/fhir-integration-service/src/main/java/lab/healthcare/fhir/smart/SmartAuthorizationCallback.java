package lab.healthcare.fhir.smart;

import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

/**
 * Query parameters from the OAuth redirect. Does not exchange a token.
 */
public record SmartAuthorizationCallback(String state, String code, String error, String errorDescription) {

    public SmartAuthorizationCallback(String state, String code, String error) {
        this(state, code, error, null);
    }

    public static SmartAuthorizationCallback parse(String redirectLocation) {
        if (redirectLocation == null || redirectLocation.isBlank()) {
            throw new SmartAuthorizationException("SMART authorization failed: missing redirect");
        }
        Map<String, String> params = queryParams(redirectLocation);
        String errorDescription = blankToNull(params.get("error_description"));
        String errorUri = blankToNull(params.get("error_uri"));
        if (isLaunchCodeRequired(errorDescription, errorUri)) {
            errorDescription = "launch:code-required";
        }
        return new SmartAuthorizationCallback(
                blankToNull(params.get("state")),
                blankToNull(params.get("code")),
                blankToNull(params.get("error")),
                errorDescription);
    }

    public static SmartAuthorizationCallback fromRedirect(String redirectLocation) {
        SmartAuthorizationCallback callback = parse(redirectLocation);
        if (callback.error() != null) {
            throw new SmartAuthorizationException(
                    "SMART authorization failed: " + callback.error());
        }
        if (callback.state() == null) {
            throw new SmartAuthorizationException("SMART authorization failed: missing state");
        }
        if (callback.code() == null) {
            throw new SmartAuthorizationException("SMART authorization failed: missing authorization code");
        }
        return callback;
    }

    public boolean hasOAuthError() {
        return error != null && !error.isBlank();
    }

    @Override
    public String toString() {
        return "SmartAuthorizationCallback[hasState="
                + (state != null && !state.isBlank())
                + ", hasCode="
                + (code != null && !code.isBlank())
                + ", error="
                + error
                + "]";
    }

    static boolean isLaunchCodeRequired(String errorDescription, String errorUri) {
        String combined = ((errorDescription == null ? "" : errorDescription)
                + " "
                + (errorUri == null ? "" : errorUri)).toLowerCase(Locale.ROOT);
        return combined.contains("launch") && combined.contains("code-required");
    }

    private static String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value;
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

    private static String decode(String value) {
        return URLDecoder.decode(value, StandardCharsets.UTF_8);
    }
}
