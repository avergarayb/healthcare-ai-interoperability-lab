package lab.healthcare.fhir.clinicalread.web;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;
import lab.healthcare.fhir.clinicalread.ClinicalReadService;

import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class ClinicalReadController {

    private static final Logger log = LoggerFactory.getLogger(ClinicalReadController.class);

    private final ClinicalReadService clinicalRead;

    public ClinicalReadController(ClinicalReadService clinicalRead) {
        if (clinicalRead == null) {
            throw new IllegalArgumentException("Clinical read service must be provided");
        }
        this.clinicalRead = clinicalRead;
    }

    @GetMapping(path = "/api/clinical-read/v1/patients/{logicalId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public JsonNode readPatient(@PathVariable String logicalId) {
        return clinicalRead.readPatient(logicalId);
    }

    @GetMapping(path = "/api/clinical-read/v1/patients", produces = MediaType.APPLICATION_JSON_VALUE)
    public JsonNode searchPatients(
            @RequestParam(required = false) String identifierSystem,
            @RequestParam(required = false) String identifierValue) {
        return clinicalRead.searchPatients(identifierSystem, identifierValue);
    }

    @GetMapping(path = "/api/clinical-read/v1/encounters/{logicalId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public JsonNode readEncounter(@PathVariable String logicalId) {
        return clinicalRead.readEncounter(logicalId);
    }

    @GetMapping(path = "/api/clinical-read/v1/encounters", produces = MediaType.APPLICATION_JSON_VALUE)
    public JsonNode searchEncounters(
            @RequestParam(required = false) String patient,
            @RequestParam(required = false) String status) {
        return clinicalRead.searchEncounters(patient, status);
    }

    @GetMapping(path = "/api/clinical-read/v1/observations/{logicalId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public JsonNode readObservation(@PathVariable String logicalId) {
        return clinicalRead.readObservation(logicalId);
    }

    @GetMapping(path = "/api/clinical-read/v1/observations", produces = MediaType.APPLICATION_JSON_VALUE)
    public JsonNode searchObservations(
            @RequestParam(required = false) String patient,
            @RequestParam(required = false) String status) {
        return clinicalRead.searchObservations(patient, status);
    }

    @GetMapping(path = "/api/clinical-read/v1/appointments/{logicalId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public JsonNode readAppointment(@PathVariable String logicalId) {
        return clinicalRead.readAppointment(logicalId);
    }

    @GetMapping(path = "/api/clinical-read/v1/appointments", produces = MediaType.APPLICATION_JSON_VALUE)
    public JsonNode searchAppointments(@RequestParam(required = false) String patient) {
        return clinicalRead.searchAppointments(patient);
    }

    @GetMapping(path = "/api/clinical-read/v1/service-requests/{logicalId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public JsonNode readServiceRequest(@PathVariable String logicalId) {
        return clinicalRead.readServiceRequest(logicalId);
    }

    @GetMapping(path = "/api/clinical-read/v1/service-requests", produces = MediaType.APPLICATION_JSON_VALUE)
    public JsonNode searchServiceRequests(
            @RequestParam(required = false) String patient,
            @RequestParam(required = false) String status) {
        return clinicalRead.searchServiceRequests(patient, status);
    }

    @GetMapping(path = "/api/clinical-read/v1/diagnostic-reports/{logicalId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public JsonNode readDiagnosticReport(@PathVariable String logicalId) {
        return clinicalRead.readDiagnosticReport(logicalId);
    }

    @GetMapping(path = "/api/clinical-read/v1/diagnostic-reports", produces = MediaType.APPLICATION_JSON_VALUE)
    public JsonNode searchDiagnosticReports(
            @RequestParam(required = false) String patient,
            @RequestParam(required = false) String status) {
        return clinicalRead.searchDiagnosticReports(patient, status);
    }

    @ExceptionHandler(ClinicalReadException.class)
    public ResponseEntity<Map<String, String>> failed(ClinicalReadException ex) {
        log.info("clinical_read_failed error={}", ex.code());
        return ResponseEntity.status(ex.httpStatus()).body(Map.of("error", ex.code()));
    }
}
