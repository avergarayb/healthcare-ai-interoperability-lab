package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.routing.FhirConditionSearchOutcome;
import lab.healthcare.fhir.routing.FhirConditionSearchResult;
import lab.healthcare.fhir.smart.web.SmartLabPages;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Laboratory diagnosis page for an authenticated Condition search by Patient.
 * Not a clinical API and not a product UI.
 */
@RestController
public class EpicSandboxConditionSearchController {

    private static final Logger log = LoggerFactory.getLogger(EpicSandboxConditionSearchController.class);

    private final EpicSandboxConditionSearchService conditionSearchService;
    private final EpicIntegrationProfile profile;

    public EpicSandboxConditionSearchController(
            EpicSandboxConditionSearchService conditionSearchService, EpicIntegrationProfile profile) {
        this.conditionSearchService = conditionSearchService;
        this.profile = profile;
    }

    @GetMapping(path = "/epic/sandbox/fhir/condition-search", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> conditionSearch() {
        FhirConditionSearchResult result = conditionSearchService.searchConditions(profile);
        log.info(
                "Epic authenticated Condition search destination={} outcome={} status={} hasEntries={}",
                result.destination(),
                result.outcome(),
                result.httpStatus(),
                result.hasEntries());
        return ResponseEntity.status(httpStatus(result.outcome())).body(SmartLabPages.epicCondition(result));
    }

    private static int httpStatus(FhirConditionSearchOutcome outcome) {
        return switch (outcome) {
            case CONDITION_SEARCH_SUCCEEDED -> 200;
            case AUTHENTICATION_REQUIRED, AUTHENTICATION_REJECTED -> 401;
            case AUTHORIZATION_DENIED -> 403;
            case PATIENT_CONTEXT_NOT_CONFIGURED, CAPABILITY_UNSUPPORTED -> 409;
            case DEPENDENCY_FAILURE -> 502;
        };
    }
}
