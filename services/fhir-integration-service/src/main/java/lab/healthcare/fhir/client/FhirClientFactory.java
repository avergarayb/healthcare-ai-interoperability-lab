package lab.healthcare.fhir.client;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.context.FhirVersionEnum;
import ca.uhn.fhir.rest.client.api.IGenericClient;

import java.util.Locale;

public class FhirClientFactory {

    public FhirContext createContext(FhirServerProfile profile) {
        requireProfile(profile);
        return FhirContext.forVersion(fhirVersion(profile));
    }

    public IGenericClient createClient(FhirContext fhirContext, FhirServerProfile profile) {
        requireProfile(profile);
        if (profile.authentication().requiresBearerToken()) {
            throw new IllegalArgumentException(
                    "FHIR server profile '" + profile.name() + "' requires an AccessTokenProvider");
        }
        return createClient(fhirContext, profile, AccessTokenProvider.none());
    }

    public IGenericClient createClient(
            FhirContext fhirContext,
            FhirServerProfile profile,
            AccessTokenProvider tokenProvider) {
        if (fhirContext == null) {
            throw new IllegalArgumentException("FhirContext must be provided");
        }
        requireProfile(profile);
        fhirVersion(profile);
        IGenericClient client = fhirContext.newRestfulGenericClient(profile.baseUrl());
        if (profile.authentication().requiresBearerToken()) {
            if (tokenProvider == null) {
                throw new IllegalArgumentException("Access token provider must be provided");
            }
            client.registerInterceptor(new BearerAccessTokenInterceptor(tokenProvider));
        }
        return client;
    }

    FhirVersionEnum fhirVersion(FhirServerProfile profile) {
        requireProfile(profile);
        String configured = profile.fhirVersion();
        FhirVersionEnum version;
        try {
            version = FhirVersionEnum.valueOf(configured.toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException ex) {
            throw new IllegalStateException(
                    "FHIR server profile '" + profile.name() + "' has unsupported fhir-version '" + configured + "'",
                    ex);
        }
        if (version != FhirVersionEnum.R4) {
            throw new IllegalStateException(
                    "FHIR server profile '" + profile.name() + "' must use R4; got " + version);
        }
        return version;
    }

    private static void requireProfile(FhirServerProfile profile) {
        if (profile == null) {
            throw new IllegalArgumentException("FHIR server profile must be provided");
        }
    }
}
