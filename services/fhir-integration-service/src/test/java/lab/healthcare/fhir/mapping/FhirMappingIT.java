package lab.healthcare.fhir.mapping;

import lab.healthcare.fhir.client.FhirService;

import ca.uhn.fhir.rest.api.MethodOutcome;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.OperationOutcome;
import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class FhirMappingIT {

    @Autowired
    private MappingService mappingService;

    @Autowired
    private FhirService fhirService;

    @Test
    void mappedResourcesRoundTripThroughHapiWithoutChangingFhirService() {
        Patient mappedPatient = mappingService.mapPatient(
                """
                {
                  "patient_id": "MAP-019-001",
                  "first_name": "John",
                  "last_name": "Smith",
                  "date_of_birth": "1980-05-20"
                }
                """,
                LabMappingDefinitions.patient());
        OperationOutcome patientValidation = fhirService.operationOutcome(fhirService.validateResource(mappedPatient));
        assertThat(fhirService.hasErrorIssue(patientValidation)).isFalse();

        MethodOutcome createdPatient = fhirService.createPatient(mappedPatient);
        String patientId = fhirService.createdLogicalId(createdPatient);
        String observationId = null;
        try {
            Patient storedPatient = fhirService.readPatient(patientId);
            assertThat(storedPatient.getIdentifierFirstRep().getValue()).isEqualTo("MAP-019-001");
            assertThat(storedPatient.getNameFirstRep().getGivenAsSingleString()).isEqualTo("John");
            assertThat(storedPatient.getNameFirstRep().getFamily()).isEqualTo("Smith");
            assertThat(storedPatient.getBirthDateElement().getValueAsString()).isEqualTo("1980-05-20");

            Observation mappedObservation = mappingService.mapObservation(
                    """
                    {
                      "patient_id": "%s",
                      "code": "85354-9",
                      "value": 120,
                      "unit": "mmHg"
                    }
                    """.formatted(patientId),
                    LabMappingDefinitions.observation());
            OperationOutcome observationValidation =
                    fhirService.operationOutcome(fhirService.validateResource(mappedObservation));
            assertThat(fhirService.hasErrorIssue(observationValidation)).isFalse();

            observationId = fhirService.createdLogicalId(fhirService.createObservation(mappedObservation));
            Observation storedObservation = fhirService.readObservation(observationId);
            assertThat(storedObservation.getSubject().getReferenceElement().getIdPart()).isEqualTo(patientId);
            assertThat(storedObservation.getCode().getCodingFirstRep().getSystem())
                    .isEqualTo(LabMappingDefinitions.LOINC);
            assertThat(storedObservation.getCode().getCodingFirstRep().getCode()).isEqualTo("85354-9");
            assertThat(storedObservation.getValueQuantity().getValue()).isEqualByComparingTo(new BigDecimal("120"));
            assertThat(storedObservation.getValueQuantity().getUnit()).isEqualTo("mmHg");
        } finally {
            if (observationId != null) {
                fhirService.deleteObservation(observationId);
            }
            fhirService.deletePatient(patientId);
        }
    }
}
