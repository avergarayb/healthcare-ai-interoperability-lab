package lab.healthcare.fhir.terminology;

import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Immutable Mini HIS unit translations. Unknown units stay uncoded.
 */
public final class StaticQuantityUnitRegistry implements QuantityUnitRegistry {

    public static final String MINI_HIS = StaticTerminologyRegistry.MINI_HIS;
    public static final String MAP_SET_VERSION = "mini-his-ucum-v1";
    public static final String UCUM_SYSTEM = "http://unitsofmeasure.org";

    private static final StaticQuantityUnitRegistry MINI_HIS_UNITS = new StaticQuantityUnitRegistry(List.of(
            unit("g/dL", "g/dL", "g/dL"),
            unit("mmHg", "mmHg", "mm[Hg]")));

    private final Map<String, QuantityUnitMapping> mappings;

    private StaticQuantityUnitRegistry(List<QuantityUnitMapping> mappings) {
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

    @Override
    public String mapSetVersion() {
        return MAP_SET_VERSION;
    }

    @Override
    public Optional<QuantityUnitMapping> find(String integrationId, String sourceUnit) {
        if (integrationId == null || sourceUnit == null || sourceUnit.isBlank()) {
            return Optional.empty();
        }
        return Optional.ofNullable(mappings.get(key(integrationId, sourceUnit)));
    }

    private static QuantityUnitMapping unit(String sourceUnit, String unitText, String code) {
        return new QuantityUnitMapping(MINI_HIS, sourceUnit, unitText, UCUM_SYSTEM, code, MAP_SET_VERSION);
    }

    private static String key(String integrationId, String sourceUnit) {
        return integrationId + "\n" + sourceUnit;
    }
}
