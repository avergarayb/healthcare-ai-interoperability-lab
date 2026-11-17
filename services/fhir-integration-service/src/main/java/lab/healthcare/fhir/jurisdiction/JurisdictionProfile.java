package lab.healthcare.fhir.jurisdiction;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import lab.healthcare.fhir.federation.JurisdictionBinding;
import lab.healthcare.fhir.interop.SourceRegistry.SourceDescriptor;

import java.util.List;
import java.util.Map;

/**
 * Closed demonstration profiles. These records cite published guides.
 * They are not national conformance claims and they are not official StructureDefinitions.
 */
public record JurisdictionProfile(
        String id,
        String version,
        String jurisdiction,
        String fhirVersion,
        String guideName,
        String guideVersion,
        String guideStatus,
        String guideUrl,
        String informativeReference,
        String organizationId,
        String policyRef,
        String sourceKey,
        String authorizationId,
        String patientSystem,
        String patientValue,
        String logicalId,
        String baseUrl,
        List<LabQuantity> observations) {

    public static final String OPERATION_ID = "jurisdiction-lab-summary-v1";
    public static final String VALIDATION_CLASS = "internal-demo-rules";
    public static final String PROFILE_TAG = "https://lab.local/jurisdiction/profile";
    public static final String VERSION_TAG = "https://lab.local/jurisdiction/profile-version";
    public static final String VALIDATION_TAG = "https://lab.local/jurisdiction/validation";
    public static final String LOINC = "http://loinc.org";
    public static final String UCUM = "http://unitsofmeasure.org";

    private static final Map<String, JurisdictionProfile> PROFILES = Map.of(
            "pe-lab-demo-v1", peru(),
            "es-lab-demo-v1", spain());

    public static JurisdictionProfile require(String id) {
        JurisdictionProfile profile = PROFILES.get(id);
        if (profile == null) {
            throw new IllegalStateException(id == null || id.isBlank() ? "profile_unknown" : "profile_version_unavailable");
        }
        return profile;
    }

    public SourceDescriptor descriptor() {
        return new SourceDescriptor(
                sourceKey, organizationId, "Jurisdiction lab demo " + jurisdiction, baseUrl,
                List.of("patient", "observation"));
    }

    public JurisdictionBinding binding() {
        return new JurisdictionBinding(patientSystem, patientValue, logicalId);
    }

    public List<ObjectNode> resources(ObjectMapper json) {
        ObjectNode patient = json.createObjectNode();
        patient.put("resourceType", "Patient");
        patient.put("id", logicalId);
        patient.putArray("identifier").addObject().put("system", patientSystem).put("value", patientValue);
        ArrayNode resources = json.createArrayNode();
        resources.add(patient);
        for (LabQuantity observation : observations) {
            ObjectNode resource = json.createObjectNode();
            resource.put("resourceType", "Observation");
            resource.put("id", observation.id());
            resource.put("status", "final");
            resource.putObject("subject").put("reference", "Patient/" + logicalId);
            resource.putObject("code").putArray("coding").addObject().put("system", LOINC).put("code", observation.code());
            resource.putObject("valueQuantity")
                    .put("value", observation.value())
                    .put("unit", observation.unit())
                    .put("system", UCUM)
                    .put("code", observation.unit());
            resources.add(resource);
        }
        List<ObjectNode> copies = new java.util.ArrayList<>();
        resources.forEach(node -> copies.add((ObjectNode) node));
        return List.copyOf(copies);
    }

    public record LabQuantity(String id, String code, double value, String unit) {
    }

    private static JurisdictionProfile peru() {
        return new JurisdictionProfile(
                "pe-lab-demo-v1", "v1", "PE", "4.0.1",
                "hl7.fhir.pe.CorePE", "0.1", "draft",
                "https://www.gob.pe/minsa/RENHICE/fhir/ImplementationGuide/hl7.fhir.pe.CorePE",
                "IPS Peru draft cited by CorePE; this profile does not validate that guide",
                "org-pe-lab-demo", "pe-lab-demo-policy-v1", "pe-lab-demo", "pe-lab-demo-001",
                "https://lab.local/jurisdiction/pe/patient", "PE-PAT-001", "pe-pat-001",
                "https://lab.local/jurisdiction/pe",
                List.of(
                        new LabQuantity("pe-obs-718-7", "718-7", 13.4, "g/dL"),
                        new LabQuantity("pe-obs-6690-2", "6690-2", 6.2, "10*3/uL")));
    }

    private static JurisdictionProfile spain() {
        return new JurisdictionProfile(
                "es-lab-demo-v1", "v1", "ES", "4.0.1",
                "hl7.fhir.eu.base", "2.0.0", "informative",
                "http://hl7.eu/fhir/base/ImplementationGuide/hl7.fhir.eu.base",
                "HL7 Europe Base and Core 2.0.0 is superseded by 2.0.1; IPS 2.0.1 is informative only",
                "org-es-lab-demo", "es-lab-demo-policy-v1", "es-lab-demo", "es-lab-demo-001",
                "https://lab.local/jurisdiction/es/patient", "ES-PAT-001", "es-pat-001",
                "https://lab.local/jurisdiction/es",
                List.of(
                        new LabQuantity("es-obs-2345-7", "2345-7", 90, "mg/dL"),
                        new LabQuantity("es-obs-4544-3", "4544-3", 42, "%")));
    }
}
