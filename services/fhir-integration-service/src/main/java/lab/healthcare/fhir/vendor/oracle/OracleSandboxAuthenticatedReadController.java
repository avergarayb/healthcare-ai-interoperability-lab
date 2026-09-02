package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.routing.FhirAuthenticatedReadOutcome;
import lab.healthcare.fhir.routing.FhirAuthenticatedReadResult;
import lab.healthcare.fhir.smart.web.SmartLabPages;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Laboratory diagnosis page for the first authenticated Patient search.
 * Not a clinical API and not a product UI.
 */
@RestController
public class OracleSandboxAuthenticatedReadController {

    private static final Logger log = LoggerFactory.getLogger(OracleSandboxAuthenticatedReadController.class);

    private final OracleSandboxAuthenticatedReadService authenticatedReadService;
    private final OracleHealthIntegrationProfile profile;

    public OracleSandboxAuthenticatedReadController(
            OracleSandboxAuthenticatedReadService authenticatedReadService,
            OracleHealthIntegrationProfile profile) {
        this.authenticatedReadService = authenticatedReadService;
        this.profile = profile;
    }

    @GetMapping(path = "/oracle/sandbox/fhir/patient-search", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> patientSearch() {
        FhirAuthenticatedReadResult result = authenticatedReadService.searchPatients(profile);
        log.info(
                "Oracle authenticated Patient search destination={} outcome={} status={}",
                result.destination(),
                result.outcome(),
                result.httpStatus());
        return ResponseEntity.status(httpStatus(result.outcome())).body(page(result));
    }

    private static int httpStatus(FhirAuthenticatedReadOutcome outcome) {
        return switch (outcome) {
            case AUTHENTICATED_READ_SUCCEEDED -> 200;
            case AUTHENTICATION_REQUIRED, AUTHENTICATION_REJECTED -> 401;
            case AUTHORIZATION_DENIED -> 403;
            case CAPABILITY_UNSUPPORTED -> 409;
            case DEPENDENCY_FAILURE -> 502;
        };
    }

    private static String page(FhirAuthenticatedReadResult result) {
        return SmartLabPages.error(
                "Oracle Health authenticated Patient search",
                "outcome=" + result.outcome()
                        + " destination=" + result.destination()
                        + " resourceType=" + result.resourceType()
                        + " responseType=" + result.responseType()
                        + " httpStatus=" + result.httpStatus()
                        + " hasEntries=" + result.hasEntries()
                        + " detail=" + result.detail());
    }
}
