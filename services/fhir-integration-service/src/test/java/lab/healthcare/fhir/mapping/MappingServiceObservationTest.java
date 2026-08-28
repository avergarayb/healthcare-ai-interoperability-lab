package lab.healthcare.fhir.mapping;

import org.hl7.fhir.r4.model.Observation;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class MappingServiceObservationTest {

    private static final String VALID_PAYLOAD = """
            {
              "patient_id": "12345",
              "code": "85354-9",
              "value": 120,
              "unit": "mmHg"
            }
            """;

    private final MappingService mappingService = new MappingService();

    @Test
    void mapsExternalJsonToHapiObservation() {
        Observation observation = mappingService.mapObservation(VALID_PAYLOAD, LabMappingDefinitions.observation());

        assertThat(observation.getSubject().getReference()).isEqualTo("Patient/12345");
        assertThat(observation.getCode().getCodingFirstRep().getSystem()).isEqualTo(LabMappingDefinitions.LOINC);
        assertThat(observation.getCode().getCodingFirstRep().getCode()).isEqualTo("85354-9");
        assertThat(observation.getValueQuantity().getValue()).isEqualByComparingTo(new BigDecimal("120"));
        assertThat(observation.getValueQuantity().getUnit()).isEqualTo("mmHg");
        assertThat(observation.getStatus()).isEqualTo(Observation.ObservationStatus.FINAL);
    }

    @Test
    void mappingDoesNotClaimTerminologyValidation() {
        Observation observation = mappingService.mapObservation(VALID_PAYLOAD, LabMappingDefinitions.observation());

        assertThat(observation.getCode().getCodingFirstRep().getCode()).isEqualTo("85354-9");
        assertThat(observation.getCode().getCodingFirstRep().hasUserSelected()).isFalse();
    }

    @Test
    void missingPatientReferenceFails() {
        assertThatThrownBy(() -> mappingService.mapObservation(
                        """
                        {
                          "code": "85354-9",
                          "value": 120,
                          "unit": "mmHg"
                        }
                        """,
                        LabMappingDefinitions.observation()))
                .isInstanceOf(MappingException.class)
                .hasMessageContaining("patient_id");
    }

    @Test
    void missingCodeFails() {
        assertThatThrownBy(() -> mappingService.mapObservation(
                        """
                        {
                          "patient_id": "12345",
                          "value": 120,
                          "unit": "mmHg"
                        }
                        """,
                        LabMappingDefinitions.observation()))
                .isInstanceOf(MappingException.class)
                .hasMessageContaining("code");
    }

    @Test
    void invalidValueFails() {
        assertThatThrownBy(() -> mappingService.mapObservation(
                        """
                        {
                          "patient_id": "12345",
                          "code": "85354-9",
                          "value": "not-a-number",
                          "unit": "mmHg"
                        }
                        """,
                        LabMappingDefinitions.observation()))
                .isInstanceOf(MappingException.class)
                .hasMessageContaining("value")
                .hasMessageContaining("not-a-number");
    }
}
