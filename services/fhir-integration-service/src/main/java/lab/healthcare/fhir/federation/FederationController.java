package lab.healthcare.fhir.federation;

import com.fasterxml.jackson.databind.JsonNode;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import jakarta.servlet.http.HttpServletRequest;

import java.util.Map;

@RestController
public class FederationController {

    private static final Logger log = LoggerFactory.getLogger(FederationController.class);

    private final FederationService federation;

    public FederationController(FederationService federation) {
        this.federation = federation;
    }

    @PostMapping(
            path = "/api/clinical-federation/v1/context",
            consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public JsonNode context(HttpServletRequest request, @RequestBody JsonNode body) {
        Object caller = request.getAttribute(FederationSecurityConfiguration.CALLER_ATTRIBUTE);
        if (!(caller instanceof String system) || system.isBlank()) {
            throw FederationException.forbidden("unauthenticated");
        }
        return federation.query(system, body);
    }

    @ExceptionHandler(FederationException.class)
    public ResponseEntity<Map<String, String>> failed(FederationException ex) {
        log.info("federation_rejected error={}", ex.code());
        return ResponseEntity.status(ex.httpStatus()).body(Map.of("error", ex.code()));
    }
}
