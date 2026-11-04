package lab.healthcare.fhir.iam;

import jakarta.servlet.http.HttpServletRequest;
import java.time.Instant;
import java.util.Map;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@ConditionalOnProperty(name = "iam.java.workload.lab.enabled", havingValue = "true")
class JavaOidcController {
    @GetMapping(JavaOidcTrust.ROUTE)
    ResponseEntity<?> context(HttpServletRequest request) {
        if (!(request.getAttribute(JavaOidcBoundary.CONTEXT) instanceof JavaPrincipalContext context)
                || !context.expiresAt().isAfter(Instant.now())) {
            return ResponseEntity.status(401).header("Cache-Control", "no-store").header("WWW-Authenticate", "Bearer")
                    .body(Map.of("error", "unauthorized"));
        }
        return ResponseEntity.ok().header("Cache-Control", "no-store").body(context.projection());
    }
}
