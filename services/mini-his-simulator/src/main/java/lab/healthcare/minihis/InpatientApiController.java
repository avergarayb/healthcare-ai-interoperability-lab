package lab.healthcare.minihis;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Map;

@RestController
public class InpatientApiController {

    private final InpatientStore store;
    private final String serviceToken;

    public InpatientApiController(
            InpatientStore store,
            @Value("${mini-his.inpatient.service-token:}") String serviceToken) {
        this.store = store;
        this.serviceToken = serviceToken == null ? "" : serviceToken.trim();
    }

    @GetMapping(path = "/api/inpatient/episodes/{episodeId}/chart", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<?> chart(
            @PathVariable String episodeId,
            @org.springframework.web.bind.annotation.RequestHeader(name = "X-Service-Token", required = false) String presented) {
        if (!authorized(presented)) {
            return ResponseEntity.status(401).body(Map.of("error", "unauthorized"));
        }
        try {
            return ResponseEntity.ok(store.chart(episodeId));
        } catch (InpatientRejection ex) {
            return ResponseEntity.status(ex.status()).body(Map.of("error", ex.code()));
        }
    }

    private boolean authorized(String presented) {
        if (serviceToken.isBlank() || presented == null || presented.isBlank()) {
            return false;
        }
        return MessageDigest.isEqual(
                serviceToken.getBytes(StandardCharsets.UTF_8),
                presented.getBytes(StandardCharsets.UTF_8));
    }
}
