package lab.healthcare.fhir.mapping;

import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Resource;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class MappingServiceGenericTest {

    private final MappingService mappingService = new MappingService();

    @Test
    void mapsSingleSourceFieldToTarget() {
        MappingDefinition definition = new MappingDefinition(
                "Patient",
                List.of(FieldMapping.from("patient_id", "identifier.value")));

        Resource resource = mappingService.map("""
                {"patient_id":"12345"}
                """, definition);

        assertThat(resource).isInstanceOf(Patient.class);
        assertThat(((Patient) resource).getIdentifierFirstRep().getValue()).isEqualTo("12345");
    }

    @Test
    void mapsMultipleSourceFields() {
        MappingDefinition definition = new MappingDefinition(
                "Patient",
                List.of(
                        FieldMapping.from("patient_id", "identifier.value"),
                        FieldMapping.from("last_name", "name.family")));

        Patient patient = mappingService.mapPatient("""
                {"patient_id":"12345","last_name":"Smith"}
                """, definition);

        assertThat(patient.getIdentifierFirstRep().getValue()).isEqualTo("12345");
        assertThat(patient.getNameFirstRep().getFamily()).isEqualTo("Smith");
        assertThat(patient.getNameFirstRep().hasGiven()).isFalse();
    }

    @Test
    void missingSourceFieldFails() {
        MappingDefinition definition = new MappingDefinition(
                "Patient",
                List.of(FieldMapping.from("patient_id", "identifier.value")));

        assertThatThrownBy(() -> mappingService.map("{}", definition))
                .isInstanceOf(MappingException.class)
                .hasMessageContaining("patient_id");
    }

    @Test
    void unsupportedTargetFails() {
        MappingDefinition definition = new MappingDefinition(
                "Patient",
                List.of(FieldMapping.from("patient_id", "gender")));

        assertThatThrownBy(() -> mappingService.map("""
                {"patient_id":"12345"}
                """, definition))
                .isInstanceOf(MappingException.class)
                .hasMessageContaining("gender");
    }

    @Test
    void invalidJsonFails() {
        assertThatThrownBy(() -> mappingService.map("{", LabMappingDefinitions.patient()))
                .isInstanceOf(MappingException.class)
                .hasMessageContaining("valid JSON");
    }

    @Test
    void nullDefinitionFails() {
        assertThatThrownBy(() -> mappingService.map("{}", null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Mapping definition");
    }
}
