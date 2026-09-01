package lab.healthcare.fhir.capability;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class FhirInteractionTest {

    @Test
    void mapsKnownCapabilityStatementCodes() {
        assertThat(FhirInteraction.fromCode("read")).contains(FhirInteraction.READ);
        assertThat(FhirInteraction.fromCode("SEARCH-TYPE")).contains(FhirInteraction.SEARCH_TYPE);
        assertThat(FhirInteraction.fromCode("create")).contains(FhirInteraction.CREATE);
        assertThat(FhirInteraction.fromCode("update")).contains(FhirInteraction.UPDATE);
        assertThat(FhirInteraction.fromCode("delete")).contains(FhirInteraction.DELETE);
        assertThat(FhirInteraction.READ.code()).isEqualTo("read");
        assertThat(FhirInteraction.SEARCH_TYPE.code()).isEqualTo("search-type");
    }

    @Test
    void unknownCodesAreOmittedNotInvented() {
        assertThat(FhirInteraction.fromCode("vread")).isEmpty();
        assertThat(FhirInteraction.fromCode("history-instance")).isEmpty();
        assertThat(FhirInteraction.fromCode("patch")).isEmpty();
        assertThat(FhirInteraction.fromCode("unknown")).isEmpty();
        assertThat(FhirInteraction.fromCode(null)).isEmpty();
        assertThat(FhirInteraction.fromCode("  ")).isEmpty();
    }
}
