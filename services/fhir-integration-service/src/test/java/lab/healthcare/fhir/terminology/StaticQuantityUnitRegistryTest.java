package lab.healthcare.fhir.terminology;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class StaticQuantityUnitRegistryTest {

    private final QuantityUnitRegistry registry = StaticQuantityUnitRegistry.miniHis();

    @Test
    void codesOnlyTheTwoKnownMiniHisUnits() {
        QuantityUnitMapping grams = registry.find(StaticQuantityUnitRegistry.MINI_HIS, "g/dL").orElseThrow();
        QuantityUnitMapping pressure = registry.find(StaticQuantityUnitRegistry.MINI_HIS, "mmHg").orElseThrow();

        assertThat(grams.unitText()).isEqualTo("g/dL");
        assertThat(grams.code()).isEqualTo("g/dL");
        assertThat(pressure.unitText()).isEqualTo("mmHg");
        assertThat(pressure.code()).isEqualTo("mm[Hg]");
        assertThat(grams.system()).isEqualTo(StaticQuantityUnitRegistry.UCUM_SYSTEM);
        assertThat(pressure.system()).isEqualTo("http://unitsofmeasure.org");
        assertThat(grams.mapSetVersion()).isEqualTo("mini-his-ucum-v1");
        assertThat(registry.mapSetVersion()).isEqualTo(StaticQuantityUnitRegistry.MAP_SET_VERSION);
        assertThat(registry.mapSetVersion()).isNotEqualTo(StaticTerminologyRegistry.MAP_SET_VERSION);
    }

    @Test
    void leavesUnknownUnitsUncoded() {
        assertThat(registry.find(StaticQuantityUnitRegistry.MINI_HIS, "mg/dL")).isEmpty();
        assertThat(registry.find(StaticQuantityUnitRegistry.MINI_HIS, "MMHG")).isEmpty();
        assertThat(registry.find("epic-sandbox", "mmHg")).isEmpty();
        assertThat(registry.find(StaticQuantityUnitRegistry.MINI_HIS, " ")).isEmpty();
    }
}
