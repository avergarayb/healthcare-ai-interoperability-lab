package lab.healthcare.fhir.clinicalread.minilis;

import com.fasterxml.jackson.databind.JsonNode;

public interface MiniLisClinicalSource {

    JsonNode readPatient(String logicalId);

    JsonNode searchPatients(String identifierSystem, String identifierValue);

    JsonNode readServiceRequest(String logicalId);

    JsonNode searchServiceRequests(String patientId, String status);

    JsonNode readObservation(String logicalId);

    JsonNode searchObservations(String patientId, String status);

    JsonNode readDiagnosticReport(String logicalId);

    JsonNode searchDiagnosticReports(String patientId, String status);
}
