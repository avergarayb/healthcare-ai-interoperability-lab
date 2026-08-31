package lab.healthcare.fhir.vendor.epic;

import java.util.Locale;

/**
 * Client authentication choices relevant to Epic. Only {@link #PUBLIC_PKCE} is implemented
 * by the current SMART runtime. The others are represented, not faked.
 */
public enum EpicClientAuthentication {
    PUBLIC_PKCE,
    CLIENT_SECRET,
    PRIVATE_KEY_JWT;

    static EpicClientAuthentication fromConfiguration(String value) {
        if (value == null || value.isBlank()) {
            return PUBLIC_PKCE;
        }
        String normalized = value.trim().toUpperCase(Locale.ROOT).replace('-', '_');
        return valueOf(normalized);
    }

    public boolean runtimeSupported() {
        return this == PUBLIC_PKCE;
    }
}
