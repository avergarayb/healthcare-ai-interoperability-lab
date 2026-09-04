package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.routing.FhirMedicationRequestSearchOutcome;
import lab.healthcare.fhir.routing.FhirMedicationRequestSearchResult;
import lab.healthcare.fhir.smart.web.SmartLabPages;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Laboratory diagnosis page for an authenticated MedicationRequest search by Patient.
 * Not a clinical API and not a product UI.
 */
@RestController
public class OracleSandboxMedicationRequestSearchController {

    private static final Logger log = LoggerFactory.getLogger(OracleSandboxMedicationRequestSearchController.class);

    private final OracleSandboxMedicationRequestSearchService medicationRequestSearchService;
    private final OracleHealthIntegrationProfile profile;

    public OracleSandboxMedicationRequestSearchController(
            OracleSandboxMedicationRequestSearchService medicationRequestSearchService,
            OracleHealthIntegrationProfile profile) {
        this.medicationRequestSearchService = medicationRequestSearchService;
        this.profile = profile;
    }

    @GetMapping(path = "/oracle/sandbox/fhir/medication-request-search", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> medicationRequestSearch() {
        FhirMedicationRequestSearchResult result = medicationRequestSearchService.searchMedicationRequests(profile);
        log.info(
                "Oracle authenticated MedicationRequest search destination={} outcome={} status={} hasEntries={}",
                result.destination(),
                result.outcome(),
                result.httpStatus(),
                result.hasEntries());
        return ResponseEntity.status(httpStatus(result.outcome())).body(page(result));
    }

    private static int httpStatus(FhirMedicationRequestSearchOutcome outcome) {
        return switch (outcome) {
            case MEDICATION_REQUEST_SEARCH_SUCCEEDED -> 200;
            case AUTHENTICATION_REQUIRED, AUTHENTICATION_REJECTED -> 401;
            case AUTHORIZATION_DENIED -> 403;
            case PATIENT_CONTEXT_NOT_CONFIGURED, CAPABILITY_UNSUPPORTED -> 409;
            case DEPENDENCY_FAILURE -> 502;
        };
    }

    private static String page(FhirMedicationRequestSearchResult result) {
        return SmartLabPages.error(
                "Oracle Health authenticated MedicationRequest search",
                "outcome=" + result.outcome()
                        + " destination=" + result.destination()
                        + " resourceType=" + result.resourceType()
                        + " responseType=" + result.responseType()
                        + " httpStatus=" + result.httpStatus()
                        + " contextSource=" + result.contextSource()
                        + " hasPatientContext=" + result.hasPatientContext()
                        + " hasEntries=" + result.hasEntries()
                        + " detail=" + result.detail());
    }
}
