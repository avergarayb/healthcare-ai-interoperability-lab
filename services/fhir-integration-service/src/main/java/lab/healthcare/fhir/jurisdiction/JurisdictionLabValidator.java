package lab.healthcare.fhir.jurisdiction;

import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

/**
 * Internal demonstration checks for one selected profile.
 * A passing result is not FHIR profile validation and not national conformance.
 */
public final class JurisdictionLabValidator {

    private JurisdictionLabValidator() {
    }

    public static String validate(JurisdictionProfile profile, ObjectNode resource) {
        if (profile == null) {
            return "profile_unknown";
        }
        if (resource == null || !resource.path("resourceType").isTextual() || resource.path("id").asText("").isBlank()) {
            return "response_rejected";
        }
        if (claimsOfficialProfile(resource)) {
            return "profile_not_verified";
        }
        String type = resource.path("resourceType").asText();
        if ("Patient".equals(type)) {
            return validatePatient(profile, resource);
        }
        if ("Observation".equals(type)) {
            return validateObservation(profile, resource);
        }
        return "response_rejected";
    }

    public static void stamp(JurisdictionProfile profile, ObjectNode resource) {
        ObjectNode meta = resource.putObject("meta");
        meta.put("source", profile.sourceKey());
        ArrayNode tags = meta.putArray("tag");
        tags.addObject().put("system", JurisdictionProfile.PROFILE_TAG).put("code", profile.id());
        tags.addObject().put("system", JurisdictionProfile.VERSION_TAG).put("code", profile.version());
        tags.addObject().put("system", JurisdictionProfile.VALIDATION_TAG).put("code", JurisdictionProfile.VALIDATION_CLASS);
        tags.addObject().put("system", JurisdictionProfile.VALIDATION_TAG).put("code", "fhir-r4-checked");
        if ("Observation".equals(resource.path("resourceType").asText())) {
            tags.addObject().put("system", JurisdictionProfile.VALIDATION_TAG).put("code", "quantity-verified");
        }
    }

    private static String validatePatient(JurisdictionProfile profile, ObjectNode resource) {
        if (!profile.logicalId().equals(resource.path("id").asText())) {
            return "context_rejected";
        }
        if (resource.has("name") || resource.has("birthDate") || resource.has("address") || resource.has("telecom")) {
            return "context_rejected";
        }
        var identifiers = resource.path("identifier");
        if (!identifiers.isArray() || identifiers.size() != 1) {
            return "context_incomplete";
        }
        var identifier = identifiers.get(0);
        if (!profile.patientSystem().equals(identifier.path("system").asText())
                || !profile.patientValue().equals(identifier.path("value").asText())) {
            return "context_rejected";
        }
        return "accepted";
    }

    private static String validateObservation(JurisdictionProfile profile, ObjectNode resource) {
        if (!"final".equals(resource.path("status").asText())) {
            return "context_incomplete";
        }
        String reference = resource.path("subject").path("reference").asText("");
        if (!("Patient/" + profile.logicalId()).equals(reference)) {
            return reference.contains("Patient/") ? "context_rejected" : "context_incomplete";
        }
        var coding = resource.path("code").path("coding");
        if (!coding.isArray() || coding.size() != 1
                || !JurisdictionProfile.LOINC.equals(coding.get(0).path("system").asText())
                || coding.get(0).path("code").asText("").isBlank()) {
            return "context_incomplete";
        }
        String code = coding.get(0).path("code").asText();
        var quantity = resource.path("valueQuantity");
        if (!quantity.isObject() || !quantity.path("value").isNumber()) {
            return "context_incomplete";
        }
        if (!JurisdictionProfile.UCUM.equals(quantity.path("system").asText())
                || !quantity.path("code").asText("").equals(quantity.path("unit").asText())) {
            return "context_rejected";
        }
        boolean known = profile.observations().stream().anyMatch(item ->
                item.code().equals(code)
                        && item.unit().equals(quantity.path("code").asText())
                        && item.value() == quantity.path("value").asDouble());
        if (!known) {
            return "context_rejected";
        }
        return "accepted";
    }

    private static boolean claimsOfficialProfile(ObjectNode resource) {
        var profiles = resource.path("meta").path("profile");
        if (!profiles.isArray()) {
            return false;
        }
        for (var profile : profiles) {
            String canonical = profile.asText("");
            if (canonical.contains("gob.pe") || canonical.contains("hl7.eu") || canonical.contains("hl7.org/fhir/uv/ips")) {
                return true;
            }
        }
        return false;
    }
}
