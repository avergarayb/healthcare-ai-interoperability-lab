package lab.healthcare.fhir.mapping;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FieldMappingTest {

    @Test
    void requiresTarget() {
        assertThatThrownBy(() -> FieldMapping.from("patient_id", " "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("target");
    }

    @Test
    void requiresSourceOrConstant() {
        assertThatThrownBy(() -> new FieldMapping(null, "identifier.value", MappingConversion.STRING, null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("source or a constant");
    }

    @Test
    void definitionRequiresResourceTypeAndFields() {
        assertThatThrownBy(() -> new MappingDefinition(" ", List.of(FieldMapping.from("a", "identifier.value"))))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("resource type");
        assertThatThrownBy(() -> new MappingDefinition("Patient", List.of()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("fields");
    }
}
