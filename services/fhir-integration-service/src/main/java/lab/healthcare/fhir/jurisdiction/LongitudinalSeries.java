package lab.healthcare.fhir.jurisdiction;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.util.List;

/**
 * Dated quantitative pairs for one demonstration profile.
 * These resources are added beside the original undated seed. They do not replace it.
 */
public final class LongitudinalSeries {

    public static final String TAG = "longitudinal-series";
    public static final String METHOD_SYSTEM = "https://lab.local/jurisdiction/method";
    public static final String METHOD_CODE = "venous-draw-v1";

    private LongitudinalSeries() {
    }

    public static List<ObjectNode> resources(JurisdictionProfile profile, ObjectMapper json) {
        if ("pe-lab-demo-v1".equals(profile.id())) {
            return List.of(
                    observation(json, profile, "pe-long-718-7-20261001", "718-7", 12.8, "g/dL",
                            "2026-10-01T08:00:00Z", "Specimen/pe-spec-718-7"),
                    observation(json, profile, "pe-long-718-7-20261115", "718-7", 13.4, "g/dL",
                            "2026-11-15T08:00:00Z", "Specimen/pe-spec-718-7"));
        }
        if ("es-lab-demo-v1".equals(profile.id())) {
            return List.of(
                    observation(json, profile, "es-long-2345-7-20261001", "2345-7", 95, "mg/dL",
                            "2026-10-01T08:00:00Z", "Specimen/es-spec-2345-7"),
                    observation(json, profile, "es-long-2345-7-20261115", "2345-7", 90, "mg/dL",
                            "2026-11-15T08:00:00Z", "Specimen/es-spec-2345-7"));
        }
        return List.of();
    }

    private static ObjectNode observation(
            ObjectMapper json, JurisdictionProfile profile, String id, String code, double value, String unit,
            String effective, String specimen) {
        ObjectNode resource = json.createObjectNode();
        resource.put("resourceType", "Observation");
        resource.put("id", id);
        resource.put("status", "final");
        resource.put("effectiveDateTime", effective);
        resource.putObject("subject").put("reference", "Patient/" + profile.logicalId());
        resource.putObject("code").putArray("coding").addObject()
                .put("system", JurisdictionProfile.LOINC).put("code", code);
        resource.putObject("valueQuantity")
                .put("value", value)
                .put("unit", unit)
                .put("system", JurisdictionProfile.UCUM)
                .put("code", unit);
        resource.putObject("specimen").put("reference", specimen);
        resource.putObject("method").putArray("coding").addObject()
                .put("system", METHOD_SYSTEM).put("code", METHOD_CODE);
        return resource;
    }
}
