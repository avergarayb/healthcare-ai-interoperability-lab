package lab.healthcare.minilis;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

@RestController
public class CriticalEventController {

    private final BenchWorkflow workflow;

    public CriticalEventController(BenchWorkflow workflow) {
        this.workflow = workflow;
    }

    @GetMapping("/orders/{orderId}/critical-event")
    public ResponseEntity<Map<String, Object>> event(@PathVariable String orderId) {
        return workflow.criticalEvent(orderId)
                .map(row -> {
                    Map<String, Object> body = new LinkedHashMap<>();
                    body.put("eventId", row.get("event_id"));
                    body.put("orderId", row.get("order_id"));
                    body.put("resultId", row.get("result_id"));
                    body.put("patientId", row.get("patient_id"));
                    body.put("organizationId", row.get("organization_id"));
                    body.put("correlationId", row.get("correlation_id"));
                    body.put("ruleId", row.get("rule_id"));
                    body.put("ruleVersion", row.get("rule_version"));
                    body.put("testCode", row.get("test_code"));
                    body.put("value", row.get("current_value"));
                    body.put("originalValue", row.get("original_value"));
                    body.put("unit", row.get("unit"));
                    body.put("status", row.get("status"));
                    body.put("recordedAt", row.get("recorded_at"));
                    body.put("correctedAt", row.get("corrected_at"));
                    body.put("simulation", true);
                    return ResponseEntity.ok(body);
                })
                .orElseGet(() -> ResponseEntity.notFound().build());
    }
}
