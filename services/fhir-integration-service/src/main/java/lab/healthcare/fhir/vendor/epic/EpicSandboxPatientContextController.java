package lab.healthcare.fhir.vendor.epic;

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
public class EpicSandboxPatientContextController {

    private static final Logger log = LoggerFactory.getLogger(EpicSandboxPatientContextController.class);

    private final EpicSandboxPatientContextService patientContextService;
    private final EpicIntegrationProfile profile;

    public EpicSandboxPatientContextController(
            EpicSandboxPatientContextService patientContextService, EpicIntegrationProfile profile) {
        this.patientContextService = patientContextService;
        this.profile = profile;
    }

    @GetMapping(path = "/epic/sandbox/fhir/patient", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> patient() {
        FhirPatientReadResult result = patientContextService.readPatient(profile);
        log.info(
                "Epic controlled Patient read destination={} outcome={} status={} hasPatientContext={}",
                result.destination(),
                result.outcome(),
                result.httpStatus(),
                result.hasPatientContext());
        return ResponseEntity.status(httpStatus(result.outcome())).body(SmartLabPages.epicPatient(result));
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
}
