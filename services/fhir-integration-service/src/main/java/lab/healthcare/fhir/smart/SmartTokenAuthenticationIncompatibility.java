package lab.healthcare.fhir.smart;

/**
 * Why a public PKCE token exchange cannot proceed, based on discovery and/or
 * the token-endpoint error. Does not invent a client secret or JWT.
 */
public enum SmartTokenAuthenticationIncompatibility {
    NONE,
    CONFIDENTIAL_CLIENT_REQUIRED,
    CLIENT_SECRET_BASIC,
    PRIVATE_KEY_JWT,
    TOKEN_ENDPOINT_REJECTED,
    AUTHORIZATION_REJECTED
}
