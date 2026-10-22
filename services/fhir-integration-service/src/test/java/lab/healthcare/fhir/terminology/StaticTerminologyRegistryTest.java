package lab.healthcare.fhir.terminology;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class StaticTerminologyRegistryTest {

    private final TerminologyRegistry registry = StaticTerminologyRegistry.miniHis();

    @Test
    void resolvesEveryMiniHisMappingInItsDomain() {
        assertStatus(TerminologyDomain.ENCOUNTER_STATUS, "completed", "finished");
        assertStatus(TerminologyDomain.ENCOUNTER_STATUS, "in_progress", "in-progress");
        assertStatus(TerminologyDomain.ENCOUNTER_STATUS, "scheduled", "planned");
        assertStatus(TerminologyDomain.ENCOUNTER_STATUS, "cancelled", "cancelled");
        assertCoded(
                TerminologyDomain.ENCOUNTER_CLASS,
                "ambulatory",
                "AMB",
                StaticTerminologyRegistry.ENCOUNTER_CLASS_SYSTEM);
        assertStatus(TerminologyDomain.OBSERVATION_STATUS, "final", "final");
        assertStatus(TerminologyDomain.OBSERVATION_STATUS, "preliminary", "preliminary");
        assertStatus(TerminologyDomain.OBSERVATION_STATUS, "corrected", "corrected");
        assertCoded(
                TerminologyDomain.OBSERVATION_CATEGORY,
                "laboratory",
                "laboratory",
                StaticTerminologyRegistry.OBSERVATION_CATEGORY_SYSTEM);
        assertCoded(
                TerminologyDomain.OBSERVATION_CATEGORY,
                "vital_sign",
                "vital-signs",
                StaticTerminologyRegistry.OBSERVATION_CATEGORY_SYSTEM);
        assertStatus(TerminologyDomain.APPOINTMENT_STATUS, "not_attended", "noshow");
        assertStatus(TerminologyDomain.APPOINTMENT_STATUS, "confirmed", "booked");
        assertStatus(TerminologyDomain.APPOINTMENT_STATUS, "scheduled", "pending");
        assertStatus(TerminologyDomain.APPOINTMENT_STATUS, "completed", "fulfilled");
        assertStatus(TerminologyDomain.APPOINTMENT_STATUS, "cancelled", "cancelled");
    }

    @Test
    void rejectsUnknownCodesWrongDomainsAndOtherIntegrations() {
        assertThatThrownBy(() -> registry.resolve(
                StaticTerminologyRegistry.MINI_HIS, TerminologyDomain.ENCOUNTER_STATUS, "arrived"))
                .isInstanceOf(TerminologyMappingNotFound.class);
        assertThatThrownBy(() -> registry.resolve(
                StaticTerminologyRegistry.MINI_HIS, TerminologyDomain.APPOINTMENT_STATUS, "arrived"))
                .isInstanceOf(TerminologyMappingNotFound.class);
        assertThatThrownBy(() -> registry.resolve(
                "epic-sandbox", TerminologyDomain.ENCOUNTER_STATUS, "completed"))
                .isInstanceOf(TerminologyMappingNotFound.class);
        assertThatThrownBy(() -> registry.resolve(
                StaticTerminologyRegistry.MINI_HIS, TerminologyDomain.OBSERVATION_CATEGORY, " "))
                .isInstanceOf(TerminologyMappingNotFound.class);
    }

    @Test
    void versionsTheMapSetRatherThanAnExternalTerminology() {
        assertThat(registry.mapSetVersion()).isEqualTo(StaticTerminologyRegistry.MAP_SET_VERSION);
        TerminologyMapping mapping = registry.resolve(
                StaticTerminologyRegistry.MINI_HIS, TerminologyDomain.APPOINTMENT_STATUS, "confirmed");
        assertThat(mapping.mapSetVersion()).isEqualTo("mini-his-maps-v1");
        assertThat(mapping.integrationId()).isEqualTo(StaticTerminologyRegistry.MINI_HIS);
    }

    private void assertStatus(TerminologyDomain domain, String source, String target) {
        TerminologyMapping mapping = registry.resolve(StaticTerminologyRegistry.MINI_HIS, domain, source);
        assertThat(mapping.domain()).isEqualTo(domain);
        assertThat(mapping.sourceCode()).isEqualTo(source);
        assertThat(mapping.targetCode()).isEqualTo(target);
        assertThat(mapping.targetSystem()).isNull();
        assertThat(mapping.mapSetVersion()).isEqualTo(registry.mapSetVersion());
    }

    private void assertCoded(
            TerminologyDomain domain, String source, String target, String system) {
        TerminologyMapping mapping = registry.resolve(StaticTerminologyRegistry.MINI_HIS, domain, source);
        assertThat(mapping.targetCode()).isEqualTo(target);
        assertThat(mapping.targetSystem()).isEqualTo(system);
        assertThat(mapping.mapSetVersion()).isEqualTo(registry.mapSetVersion());
    }
}
