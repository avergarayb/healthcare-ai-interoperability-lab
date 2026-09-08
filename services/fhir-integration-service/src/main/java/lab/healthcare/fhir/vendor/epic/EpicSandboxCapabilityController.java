package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.capability.FhirCapabilityException;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.smart.web.SmartLabPages;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Laboratory diagnosis page for a public Epic sandbox GET /metadata.
 * Not a clinical API and not a product UI.
 */
@RestController
public class EpicSandboxCapabilityController {

    private static final Logger log = LoggerFactory.getLogger(EpicSandboxCapabilityController.class);

    private final EpicSandboxCapabilityDiscoveryService capabilityDiscovery;
    private final EpicIntegrationProfile profile;

    public EpicSandboxCapabilityController(
            EpicSandboxCapabilityDiscoveryService capabilityDiscovery, EpicIntegrationProfile profile) {
        this.capabilityDiscovery = capabilityDiscovery;
        this.profile = profile;
    }

    @GetMapping(path = "/epic/sandbox/fhir/capabilities", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> capabilities() {
        try {
            FhirServerCapabilities discovered = capabilityDiscovery.discover(profile);
            log.info(
                    "Epic capability discovery destination={} fhirVersion={} resourceTypes={}",
                    discovered.destination(),
                    discovered.fhirVersion(),
                    discovered.resources().size());
            return ResponseEntity.ok(SmartLabPages.epicCapabilities(
                    "SUCCESS",
                    200,
                    discovered.destination(),
                    discovered.fhirVersion(),
                    discovered.resources().size(),
                    ""));
        } catch (EpicProfileException ex) {
            log.info("Epic capability discovery rejected destination={} reason=profile", profile.serverProfileName());
            String detail = profile.enabled()
                    ? ex.getMessage()
                    : ex.getMessage()
                            + " Set EPIC_SANDBOX_ENABLED=true in the repo-root .env and restart the process.";
            return ResponseEntity.status(409)
                    .body(SmartLabPages.epicCapabilities(
                            "FAILED", 409, profile.serverProfileName(), "", 0, detail));
        } catch (FhirClientException ex) {
            int status = httpStatus(ex);
            log.info(
                    "Epic capability discovery failed destination={} category={} httpStatus={}",
                    profile.serverProfileName(),
                    ex.category(),
                    status);
            return ResponseEntity.status(status)
                    .body(SmartLabPages.epicCapabilities(
                            "FAILED",
                            status,
                            profile.serverProfileName(),
                            "",
                            0,
                            ex.details().message()));
        } catch (FhirCapabilityException ex) {
            log.info("Epic capability discovery failed destination={} reason=document", profile.serverProfileName());
            return ResponseEntity.status(502)
                    .body(SmartLabPages.epicCapabilities(
                            "FAILED", 502, profile.serverProfileName(), "", 0, ex.getMessage()));
        }
    }

    private static int httpStatus(FhirClientException ex) {
        if (ex.details().status() != null) {
            int status = ex.details().status();
            if (status == 401 || status == 403) {
                return status;
            }
        }
        return switch (ex.category()) {
            case AUTHENTICATION_ERROR -> 401;
            case AUTHORIZATION_ERROR -> 403;
            case VALIDATION_ERROR -> 409;
            default -> 502;
        };
    }
}
