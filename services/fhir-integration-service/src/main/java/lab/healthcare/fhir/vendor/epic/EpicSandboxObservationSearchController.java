package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.routing.FhirObservationSearchOutcome;
import lab.healthcare.fhir.routing.FhirObservationSearchResult;
import lab.healthcare.fhir.smart.web.SmartLabPages;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Laboratory diagnosis page for an authenticated Observation search by Patient.
 * Not a clinical API and not a product UI.
 */
@RestController
public class EpicSandboxObservationSearchController {

    private static final Logger log = LoggerFactory.getLogger(EpicSandboxObservationSearchController.class);

    private final EpicSandboxObservationSearchService observationSearchService;
    private final EpicIntegrationProfile profile;

    public EpicSandboxObservationSearchController(
            EpicSandboxObservationSearchService observationSearchService, EpicIntegrationProfile profile) {
        this.observationSearchService = observationSearchService;
        this.profile = profile;
    }

    @GetMapping(path = "/epic/sandbox/fhir/observation-search", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> observationSearch() {
        FhirObservationSearchResult result = observationSearchService.searchObservations(profile);
        log.info(
                "Epic authenticated Observation search destination={} outcome={} status={} hasEntries={}",
                result.destination(),
                result.outcome(),
                result.httpStatus(),
                result.hasEntries());
        return ResponseEntity.status(httpStatus(result.outcome())).body(SmartLabPages.epicObservation(result));
    }

    private static int httpStatus(FhirObservationSearchOutcome outcome) {
        return switch (outcome) {
            case OBSERVATION_SEARCH_SUCCEEDED -> 200;
            case AUTHENTICATION_REQUIRED, AUTHENTICATION_REJECTED -> 401;
            case AUTHORIZATION_DENIED -> 403;
            case PATIENT_CONTEXT_NOT_CONFIGURED, CAPABILITY_UNSUPPORTED -> 409;
            case DEPENDENCY_FAILURE -> 502;
        };
    }
}
