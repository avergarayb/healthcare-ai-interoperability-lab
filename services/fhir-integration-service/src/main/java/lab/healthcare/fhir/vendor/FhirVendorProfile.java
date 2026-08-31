package lab.healthcare.fhir.vendor;

/**
 * Vendor identity of a named server profile. Does not carry Epic launch or OAuth details.
 */
public record FhirVendorProfile(FhirVendor vendor, String serverProfileName) {

    public FhirVendorProfile {
        if (vendor == null) {
            vendor = FhirVendor.GENERIC;
        }
        if (serverProfileName == null || serverProfileName.isBlank()) {
            throw new IllegalArgumentException("server profile name must be provided");
        }
        serverProfileName = serverProfileName.trim();
    }
}
