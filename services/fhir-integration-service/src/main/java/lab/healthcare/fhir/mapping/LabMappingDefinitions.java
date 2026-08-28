package lab.healthcare.fhir.mapping;

import java.util.List;

/**
 * Lab example mappings. Not a customer EHR catalog and not persisted.
 */
public final class LabMappingDefinitions {

    public static final String LOINC = "http://loinc.org";

    private LabMappingDefinitions() {
    }

    public static MappingDefinition patient() {
        return new MappingDefinition(
                "Patient",
                List.of(
                        FieldMapping.from("patient_id", "identifier.value"),
                        FieldMapping.from("first_name", "name.given[0]"),
                        FieldMapping.from("last_name", "name.family"),
                        FieldMapping.from("date_of_birth", "birthDate", MappingConversion.DATE)));
    }

    public static MappingDefinition observation() {
        return new MappingDefinition(
                "Observation",
                List.of(
                        FieldMapping.from("patient_id", "subject.reference", MappingConversion.PATIENT_REFERENCE),
                        FieldMapping.from("code", "code.coding[0].code"),
                        FieldMapping.constant("code.coding[0].system", LOINC),
                        FieldMapping.from("value", "valueQuantity.value", MappingConversion.DECIMAL),
                        FieldMapping.from("unit", "valueQuantity.unit"),
                        FieldMapping.constant("status", "final")));
    }
}
