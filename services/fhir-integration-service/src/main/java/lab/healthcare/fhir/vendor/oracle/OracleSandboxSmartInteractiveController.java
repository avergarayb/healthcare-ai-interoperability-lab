package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.smart.SmartAuthorizationStart;
import lab.healthcare.fhir.smart.web.SmartLabPages;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Minimal lab page to start an Oracle sandbox SMART authorize attempt.
 * Not a product UI and not a FHIR API.
 */
@RestController
public class OracleSandboxSmartInteractiveController {

    private static final Logger log = LoggerFactory.getLogger(OracleSandboxSmartInteractiveController.class);

    private final OracleSandboxAuthenticationService authenticationService;
    private final OracleHealthIntegrationProfile profile;

    public OracleSandboxSmartInteractiveController(
            OracleSandboxAuthenticationService authenticationService, OracleHealthIntegrationProfile profile) {
        this.authenticationService = authenticationService;
        this.profile = profile;
    }

    @GetMapping(path = "/oracle/sandbox/smart", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> instructions() {
        return ResponseEntity.ok(SmartLabPages.instructions());
    }

    @GetMapping(path = "/oracle/sandbox/smart/start", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> start() {
        try {
            SmartAuthorizationStart start = authenticationService.startAuthorization(profile);
            log.info(
                    "SMART authorize started destination={} confidentialTokenAuthAdvertised={}",
                    start.destination(),
                    start.advertisesConfidentialTokenAuth());
            return ResponseEntity.ok(SmartLabPages.start(start));
        } catch (OracleHealthProfileException ex) {
            log.info("SMART authorize start rejected destination={} reason=profile", profile.serverProfileName());
            String detail = profile.enabled()
                    ? ex.getMessage()
                    : ex.getMessage()
                            + " Set ORACLE_HEALTH_SANDBOX_ENABLED=true in the repo-root .env and restart the process.";
            return ResponseEntity.status(409).body(SmartLabPages.error("Oracle sandbox is not ready", detail));
        } catch (RuntimeException ex) {
            log.info("SMART authorize start failed destination={}", profile.serverProfileName());
            return ResponseEntity.status(502)
                    .body(SmartLabPages.error("SMART discovery failed", "Discovery or compatibility failed. No token was requested."));
        }
    }
}
