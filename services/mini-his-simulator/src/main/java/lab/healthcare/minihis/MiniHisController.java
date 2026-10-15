package lab.healthcare.minihis;

import jakarta.servlet.http.HttpServletRequest;

import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class MiniHisController {

    private static final int DEFAULT_LIMIT = 50;
    private static final int MAX_LIMIT = 100;

    private final MiniHisStore store;

    public MiniHisController(MiniHisStore store) {
        this.store = store;
    }

    @GetMapping(path = "/health", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, String> health() {
        return Map.of("status", "up");
    }

    @GetMapping(path = "/patients", produces = MediaType.APPLICATION_JSON_VALUE)
    public Object patients(@RequestParam(name = "limit", required = false) Integer limit) {
        Integer bounded = boundLimit(limit);
        if (bounded == null) {
            return invalidLimit();
        }
        return store.listPatients(bounded);
    }

    @GetMapping(path = "/patients/{patientId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<?> patient(@PathVariable String patientId) {
        return store.findPatient(patientId)
                .<ResponseEntity<?>>map(ResponseEntity::ok)
                .orElseGet(MiniHisController::notFound);
    }

    @GetMapping(path = "/patients/{patientId}/consultations", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<?> consultations(
            @PathVariable String patientId,
            @RequestParam(name = "limit", required = false) Integer limit) {
        Integer bounded = boundLimit(limit);
        if (bounded == null) {
            return invalidLimit();
        }
        return store.listConsultations(patientId, bounded)
                .<ResponseEntity<?>>map(ResponseEntity::ok)
                .orElseGet(MiniHisController::notFound);
    }

    @GetMapping(path = "/consultations/{consultationId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<?> consultation(@PathVariable String consultationId) {
        return store.findConsultation(consultationId)
                .<ResponseEntity<?>>map(ResponseEntity::ok)
                .orElseGet(MiniHisController::notFound);
    }

    @GetMapping(path = "/consultations/{consultationId}/results", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<?> consultationResults(
            @PathVariable String consultationId,
            @RequestParam(name = "limit", required = false) Integer limit) {
        Integer bounded = boundLimit(limit);
        if (bounded == null) {
            return invalidLimit();
        }
        return store.listResultsForConsultation(consultationId, bounded)
                .<ResponseEntity<?>>map(ResponseEntity::ok)
                .orElseGet(MiniHisController::notFound);
    }

    @GetMapping(path = "/patients/{patientId}/results", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<?> patientResults(
            @PathVariable String patientId,
            @RequestParam(name = "limit", required = false) Integer limit) {
        Integer bounded = boundLimit(limit);
        if (bounded == null) {
            return invalidLimit();
        }
        return store.listResultsForPatient(patientId, bounded)
                .<ResponseEntity<?>>map(ResponseEntity::ok)
                .orElseGet(MiniHisController::notFound);
    }

    @PostMapping(path = "/synthetic/reset", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<?> reset(HttpServletRequest request) {
        if (!LoopbackGuard.isLoopback(request.getRemoteAddr())
                || !LoopbackGuard.isLoopback(request.getLocalAddr())) {
            return ResponseEntity.status(403).body(Map.of("error", "reset_not_local"));
        }
        return ResponseEntity.ok(store.reset());
    }

    private static Integer boundLimit(Integer limit) {
        if (limit == null) {
            return DEFAULT_LIMIT;
        }
        if (limit < 1 || limit > MAX_LIMIT) {
            return null;
        }
        return limit;
    }

    private static ResponseEntity<Map<String, String>> notFound() {
        return ResponseEntity.status(404).body(Map.of("error", "not_found"));
    }

    private static ResponseEntity<Map<String, String>> invalidLimit() {
        return ResponseEntity.badRequest().body(Map.of("error", "invalid_limit"));
    }
}
