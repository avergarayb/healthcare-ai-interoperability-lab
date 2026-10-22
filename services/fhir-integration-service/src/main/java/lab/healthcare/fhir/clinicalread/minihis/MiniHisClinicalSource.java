package lab.healthcare.fhir.clinicalread.minihis;

import com.fasterxml.jackson.databind.JsonNode;

public interface MiniHisClinicalSource {

    JsonNode readPatient(String logicalId);

    JsonNode searchPatients(String identifierSystem, String identifierValue);

    JsonNode readEncounter(String logicalId);

    JsonNode searchEncounters(String patientId, String status);

    JsonNode readObservation(String logicalId);

    JsonNode searchObservations(String patientId, String status);

    JsonNode readAppointment(String logicalId);

    JsonNode searchAppointments(String patientId);
}
