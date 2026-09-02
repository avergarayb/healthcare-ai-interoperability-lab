package lab.healthcare.fhir.smart.web;

import lab.healthcare.fhir.smart.SmartAuthorizationCoordinator;
import lab.healthcare.fhir.smart.SmartAuthorizationException;
import lab.healthcare.fhir.smart.SmartTokenExchangeResult;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import jakarta.servlet.http.HttpServletRequest;

/**
 * Local OAuth redirect target. Validates state and attempts token exchange.
 * Query strings are never logged.
 */
@RestController
public class SmartAuthorizationCallbackController {

    private static final Logger log = LoggerFactory.getLogger(SmartAuthorizationCallbackController.class);

    private final SmartAuthorizationCoordinator coordinator;

    public SmartAuthorizationCallbackController(SmartAuthorizationCoordinator coordinator) {
        this.coordinator = coordinator;
    }

    @GetMapping(path = "/smart/callback", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> callback(HttpServletRequest request) {
        try {
            SmartTokenExchangeResult result = coordinator.completeDiagnosed(redirectOf(request));
            log.info(
                    "SMART callback processed tokenIssued={} incompatibility={}",
                    result.succeeded(),
                    result.diagnosis().incompatibility());
            int status = result.succeeded() ? 200 : 409;
            return ResponseEntity.status(status).body(SmartLabPages.result(result));
        } catch (SmartAuthorizationException ex) {
            log.info("SMART callback rejected before token exchange");
            return ResponseEntity.badRequest().body(SmartLabPages.error("SMART callback rejected", ex.getMessage()));
        }
    }

    private static String redirectOf(HttpServletRequest request) {
        String query = request.getQueryString();
        String url = request.getRequestURL().toString();
        return query == null || query.isBlank() ? url : url + "?" + query;
    }
}
