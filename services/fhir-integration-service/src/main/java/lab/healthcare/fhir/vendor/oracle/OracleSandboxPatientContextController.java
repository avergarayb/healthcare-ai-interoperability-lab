package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.routing.FhirPatientReadOutcome;
import lab.healthcare.fhir.routing.FhirPatientReadResult;
import lab.healthcare.fhir.smart.web.SmartLabPages;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Laboratory diagnosis page for a controlled authenticated Patient read.
 * Not a clinical API, patient directory, or product UI.
 */
@RestController
public class OracleSandboxPatientContextController {

    private static final Logger log = LoggerFactory.getLogger(OracleSandboxPatientContextController.class);

    private final OracleSandboxPatientContextService patientContextService;
    private final OracleHealthIntegrationProfile profile;

    public OracleSandboxPatientContextController(
            OracleSandboxPatientContextService patientContextService,
            OracleHealthIntegrationProfile profile) {
        this.patientContextService = patientContextService;
        this.profile = profile;
    }

    @GetMapping(path = "/oracle/sandbox/fhir/patient", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> patient() {
        FhirPatientReadResult result = patientContextService.readPatient(profile);
        log.info(
                "Oracle controlled Patient read destination={} outcome={} status={} hasPatientContext={}",
                result.destination(),
                result.outcome(),
                result.httpStatus(),
                result.hasPatientContext());
        return ResponseEntity.status(httpStatus(result.outcome())).body(page(result));
    }

    private static int httpStatus(FhirPatientReadOutcome outcome) {
        return switch (outcome) {
            case PATIENT_READ_SUCCEEDED -> 200;
            case AUTHENTICATION_REQUIRED, AUTHENTICATION_REJECTED -> 401;
            case AUTHORIZATION_DENIED -> 403;
            case PATIENT_NOT_FOUND -> 404;
            case PATIENT_CONTEXT_NOT_CONFIGURED, CAPABILITY_UNSUPPORTED -> 409;
            case DEPENDENCY_FAILURE -> 502;
        };
    }

    private static String page(FhirPatientReadResult result) {
        return SmartLabPages.error(
                "Oracle Health controlled Patient read",
                "outcome=" + result.outcome()
                        + " destination=" + result.destination()
                        + " resourceType=" + result.resourceType()
                        + " responseType=" + result.responseType()
                        + " httpStatus=" + result.httpStatus()
                        + " contextSource=" + result.contextSource()
                        + " hasPatientContext=" + result.hasPatientContext()
                        + " detail=" + result.detail());
    }
}
