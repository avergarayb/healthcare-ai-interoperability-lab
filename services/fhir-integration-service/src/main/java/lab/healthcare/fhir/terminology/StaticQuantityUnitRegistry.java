package lab.healthcare.fhir.terminology;

import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Immutable unit translations. Unknown units stay uncoded. Numbers are not converted.
 */
public final class StaticQuantityUnitRegistry implements QuantityUnitRegistry {

    public static final String MINI_HIS = StaticTerminologyRegistry.MINI_HIS;
    public static final String MINI_LIS = "mini-lis";
    public static final String MAP_SET_VERSION = "mini-his-ucum-v1";
    public static final String MINI_LIS_MAP_SET_VERSION = "mini-lis-ucum-v1";
    public static final String UCUM_SYSTEM = "http://unitsofmeasure.org";

    private static final StaticQuantityUnitRegistry MINI_HIS_UNITS = new StaticQuantityUnitRegistry(
            MAP_SET_VERSION,
            List.of(
                    mapped(MINI_HIS, MAP_SET_VERSION, "g/dL", "g/dL", "g/dL"),
                    mapped(MINI_HIS, MAP_SET_VERSION, "mmHg", "mmHg", "mm[Hg]")));

    private static final StaticQuantityUnitRegistry MINI_LIS_UNITS = new StaticQuantityUnitRegistry(
            MINI_LIS_MAP_SET_VERSION,
            List.of(
                    mapped(MINI_LIS, MINI_LIS_MAP_SET_VERSION, "g/dL", "g/dL", "g/dL"),
                    mapped(MINI_LIS, MINI_LIS_MAP_SET_VERSION, "mg/dL", "mg/dL", "mg/dL")));

    private final String mapSetVersion;
    private final Map<String, QuantityUnitMapping> mappings;

    private StaticQuantityUnitRegistry(String mapSetVersion, List<QuantityUnitMapping> mappings) {
        this.mapSetVersion = mapSetVersion;
        Map<String, QuantityUnitMapping> indexed = new java.util.LinkedHashMap<>();
        for (QuantityUnitMapping mapping : mappings) {
            if (indexed.putIfAbsent(key(mapping.integrationId(), mapping.sourceUnit()), mapping) != null) {
                throw new IllegalStateException("Duplicate quantity unit mapping");
            }
        }
        this.mappings = Map.copyOf(indexed);
    }

    public static QuantityUnitRegistry miniHis() {
        return MINI_HIS_UNITS;
    }

    public static QuantityUnitRegistry miniLis() {
        return MINI_LIS_UNITS;
    }

    @Override
    public String mapSetVersion() {
        return mapSetVersion;
    }

    @Override
    public Optional<QuantityUnitMapping> find(String integrationId, String sourceUnit) {
        if (integrationId == null || sourceUnit == null || sourceUnit.isBlank()) {
            return Optional.empty();
        }
        return Optional.ofNullable(mappings.get(key(integrationId, sourceUnit)));
    }

    private static QuantityUnitMapping mapped(
            String integrationId,
            String version,
            String sourceUnit,
            String unitText,
            String code) {
        return new QuantityUnitMapping(integrationId, sourceUnit, unitText, UCUM_SYSTEM, code, version);
    }

    private static String key(String integrationId, String sourceUnit) {
        return integrationId + "\n" + sourceUnit;
    }
}
