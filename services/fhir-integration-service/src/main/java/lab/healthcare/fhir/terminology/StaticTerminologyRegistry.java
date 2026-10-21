package lab.healthcare.fhir.terminology;

import java.util.List;
import java.util.Map;

/**
 * Immutable Mini HIS translations already used by the FHIR normalizer.
 * The version names this map set. It is not a LOINC, SNOMED, or UCUM version.
 */
public final class StaticTerminologyRegistry implements TerminologyRegistry {

    public static final String MINI_HIS = "mini-his";
    public static final String MAP_SET_VERSION = "mini-his-maps-v1";
    public static final String ENCOUNTER_CLASS_SYSTEM = "http://terminology.hl7.org/CodeSystem/v3-ActCode";
    public static final String OBSERVATION_CATEGORY_SYSTEM =
            "http://terminology.hl7.org/CodeSystem/observation-category";

    private static final StaticTerminologyRegistry MINI_HIS_MAPS = new StaticTerminologyRegistry(List.of(
            status(TerminologyDomain.ENCOUNTER_STATUS, "completed", "finished"),
            status(TerminologyDomain.ENCOUNTER_STATUS, "in_progress", "in-progress"),
            status(TerminologyDomain.ENCOUNTER_STATUS, "scheduled", "planned"),
            status(TerminologyDomain.ENCOUNTER_STATUS, "cancelled", "cancelled"),
            coded(TerminologyDomain.ENCOUNTER_CLASS, "ambulatory", "AMB", ENCOUNTER_CLASS_SYSTEM),
            status(TerminologyDomain.OBSERVATION_STATUS, "final", "final"),
            status(TerminologyDomain.OBSERVATION_STATUS, "preliminary", "preliminary"),
            status(TerminologyDomain.OBSERVATION_STATUS, "corrected", "corrected"),
            coded(TerminologyDomain.OBSERVATION_CATEGORY, "laboratory", "laboratory", OBSERVATION_CATEGORY_SYSTEM),
            coded(TerminologyDomain.OBSERVATION_CATEGORY, "vital_sign", "vital-signs", OBSERVATION_CATEGORY_SYSTEM),
            status(TerminologyDomain.APPOINTMENT_STATUS, "not_attended", "noshow"),
            status(TerminologyDomain.APPOINTMENT_STATUS, "confirmed", "booked"),
            status(TerminologyDomain.APPOINTMENT_STATUS, "scheduled", "pending"),
            status(TerminologyDomain.APPOINTMENT_STATUS, "completed", "fulfilled"),
            status(TerminologyDomain.APPOINTMENT_STATUS, "cancelled", "cancelled")));

    private final Map<String, TerminologyMapping> mappings;

    private StaticTerminologyRegistry(List<TerminologyMapping> mappings) {
        Map<String, TerminologyMapping> indexed = new java.util.LinkedHashMap<>();
        for (TerminologyMapping mapping : mappings) {
            if (indexed.putIfAbsent(key(mapping.integrationId(), mapping.domain(), mapping.sourceCode()), mapping) != null) {
                throw new IllegalStateException("Duplicate terminology mapping");
            }
        }
        this.mappings = Map.copyOf(indexed);
    }

    public static TerminologyRegistry miniHis() {
        return MINI_HIS_MAPS;
    }

    @Override
    public String mapSetVersion() {
        return MAP_SET_VERSION;
    }

    @Override
    public TerminologyMapping resolve(String integrationId, TerminologyDomain domain, String sourceCode) {
        if (domain == null || sourceCode == null || sourceCode.isBlank()) {
            throw new TerminologyMappingNotFound(integrationId, domain, sourceCode);
        }
        TerminologyMapping mapping = mappings.get(key(integrationId, domain, sourceCode));
        if (mapping == null) {
            throw new TerminologyMappingNotFound(integrationId, domain, sourceCode);
        }
        return mapping;
    }

    private static TerminologyMapping status(TerminologyDomain domain, String sourceCode, String targetCode) {
        return new TerminologyMapping(MINI_HIS, domain, sourceCode, targetCode, null, MAP_SET_VERSION);
    }

    private static TerminologyMapping coded(
            TerminologyDomain domain, String sourceCode, String targetCode, String targetSystem) {
        return new TerminologyMapping(MINI_HIS, domain, sourceCode, targetCode, targetSystem, MAP_SET_VERSION);
    }

    private static String key(String integrationId, TerminologyDomain domain, String sourceCode) {
        return integrationId + "\n" + domain + "\n" + sourceCode;
    }
}
