package lab.healthcare.minilis;

import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class Hl7Controller {

    private final Hl7Properties properties;
    private final Hl7Server server;
    private final Hl7ResultPublisher publisher;

    public Hl7Controller(Hl7Properties properties, Hl7Server server, Hl7ResultPublisher publisher) {
        this.properties = properties;
        this.server = server;
        this.publisher = publisher;
    }

    @GetMapping(path = "/hl7/listener", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> listener() {
        return Map.of("enabled", properties.isEnabled(), "port", server.port());
    }

    @PutMapping(path = "/hl7/result-peer", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> peer(@RequestBody PeerRequest request) {
        if (!properties.isEnabled() || request == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "invalid_request"));
        }
        try {
            publisher.configurePeer(request.host(), request.port());
        } catch (MiniLisException ex) {
            return ResponseEntity.badRequest().body(Map.of("error", ex.code()));
        }
        return ResponseEntity.ok(Map.of("host", request.host(), "port", request.port()));
    }

    @org.springframework.web.bind.annotation.PostMapping(path = "/hl7/results/{resultId}/publication", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, String>> publish(@PathVariable String resultId) {
        String ack = publisher.publish(resultId);
        if ("AA".equals(ack)) {
            return ResponseEntity.ok(Map.of("ack", "AA", "resultId", resultId));
        }
        String error = "AE".equals(ack) || "AR".equals(ack) ? "destination_rejected" : "destination_unavailable";
        if ("unauthorized".equals(ack) || "not_configured".equals(ack)) {
            error = ack;
        }
        return ResponseEntity.status(503).body(Map.of("error", error, "resultId", resultId));
    }

    public record PeerRequest(String host, int port) {
    }
}
