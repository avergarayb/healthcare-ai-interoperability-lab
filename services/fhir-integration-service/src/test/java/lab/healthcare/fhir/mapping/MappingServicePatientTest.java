package lab.healthcare.fhir.mapping;

import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class MappingServicePatientTest {

    private static final String VALID_PAYLOAD = """
            {
              "patient_id": "12345",
              "first_name": "John",
              "last_name": "Smith",
              "date_of_birth": "1980-05-20"
            }
            """;

    private final MappingService mappingService = new MappingService();

    @Test
    void mapsExternalJsonToHapiPatient() {
        Patient patient = mappingService.mapPatient(VALID_PAYLOAD, LabMappingDefinitions.patient());

        assertThat(patient.getIdentifierFirstRep().getValue()).isEqualTo("12345");
        assertThat(patient.getNameFirstRep().getGivenAsSingleString()).isEqualTo("John");
        assertThat(patient.getNameFirstRep().getFamily()).isEqualTo("Smith");
        assertThat(patient.getBirthDateElement().getValueAsString()).isEqualTo("1980-05-20");
    }

    @Test
    void missingPatientIdFails() {
        assertThatThrownBy(() -> mappingService.mapPatient(
                        """
                        {
                          "first_name": "John",
                          "last_name": "Smith",
                          "date_of_birth": "1980-05-20"
                        }
                        """,
                        LabMappingDefinitions.patient()))
                .isInstanceOf(MappingException.class)
                .hasMessageContaining("patient_id");
    }

    @Test
    void missingFirstNameFails() {
        assertThatThrownBy(() -> mappingService.mapPatient(
                        """
                        {
                          "patient_id": "12345",
                          "last_name": "Smith",
                          "date_of_birth": "1980-05-20"
                        }
                        """,
                        LabMappingDefinitions.patient()))
                .isInstanceOf(MappingException.class)
                .hasMessageContaining("first_name");
    }

    @Test
    void missingLastNameFails() {
        assertThatThrownBy(() -> mappingService.mapPatient(
                        """
                        {
                          "patient_id": "12345",
                          "first_name": "John",
                          "date_of_birth": "1980-05-20"
                        }
                        """,
                        LabMappingDefinitions.patient()))
                .isInstanceOf(MappingException.class)
                .hasMessageContaining("last_name");
    }

    @Test
    void invalidBirthDateFails() {
        assertThatThrownBy(() -> mappingService.mapPatient(
                        """
                        {
                          "patient_id": "12345",
                          "first_name": "John",
                          "last_name": "Smith",
                          "date_of_birth": "not-a-date"
                        }
                        """,
                        LabMappingDefinitions.patient()))
                .isInstanceOf(MappingException.class)
                .hasMessageContaining("date_of_birth")
                .hasMessageContaining("not-a-date");
    }
}
