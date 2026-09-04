package lab.healthcare.fhir.vendor.oracle;

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
public class OracleSandboxConditionSearchController {

    private static final Logger log = LoggerFactory.getLogger(OracleSandboxConditionSearchController.class);

    private final OracleSandboxConditionSearchService conditionSearchService;
    private final OracleHealthIntegrationProfile profile;

    public OracleSandboxConditionSearchController(
            OracleSandboxConditionSearchService conditionSearchService,
            OracleHealthIntegrationProfile profile) {
        this.conditionSearchService = conditionSearchService;
        this.profile = profile;
    }

    @GetMapping(path = "/oracle/sandbox/fhir/condition-search", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> conditionSearch() {
        FhirConditionSearchResult result = conditionSearchService.searchConditions(profile);
        log.info(
                "Oracle authenticated Condition search destination={} outcome={} status={} hasEntries={}",
                result.destination(),
                result.outcome(),
                result.httpStatus(),
                result.hasEntries());
        return ResponseEntity.status(httpStatus(result.outcome())).body(page(result));
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

    private static String page(FhirConditionSearchResult result) {
        return SmartLabPages.error(
                "Oracle Health authenticated Condition search",
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
