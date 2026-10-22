package lab.healthcare.minihis;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.Map;
import java.util.regex.Pattern;

@RestController
public class LabOrderController {

    private static final Logger log = LoggerFactory.getLogger(LabOrderController.class);
    private static final Pattern ID = Pattern.compile("[A-Za-z0-9\\-.]{1,64}");

    private final MiniHisStore patients;
    private final LabOrderStore orders;
    private final ExchangeGateway exchange;
    private final MiniHisSettings settings;
    private final ObjectMapper json;

    public LabOrderController(
            MiniHisStore patients,
            LabOrderStore orders,
            ExchangeGateway exchange,
            MiniHisSettings settings,
            ObjectMapper json) {
        this.patients = patients;
        this.orders = orders;
        this.exchange = exchange;
        this.settings = settings;
        this.json = json;
    }

    @PostMapping(path = "/lab-orders", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<LabOrderView> create(@RequestBody LabOrderRequest request) {
        if (request == null
                || request.patientId() == null
                || !ID.matcher(request.patientId()).matches()
                || request.destinationSystemKey() == null
                || !ID.matcher(request.destinationSystemKey()).matches()
                || request.testCode() == null
                || !ID.matcher(request.testCode()).matches()
                || request.testDescription() == null
                || request.testDescription().isBlank()
                || request.testDescription().length() > 200
                || request.requestedAt() == null) {
            return ResponseEntity.badRequest().body(null);
        }
        try {
            OffsetDateTime.parse(request.requestedAt());
        } catch (DateTimeParseException ex) {
            return ResponseEntity.badRequest().build();
        }
        if (patients.findPatient(request.patientId()).isEmpty()) {
            return ResponseEntity.status(404).body(null);
        }
        LabOrderView created = orders.insert(
                request.patientId(),
                request.destinationSystemKey(),
                request.testCode(),
                request.testDescription().trim(),
                request.requestedAt());
        log.info("mini_his_lab_order_recorded id={} patient={}", created.orderId(), created.patientId());
        return ResponseEntity.status(201).body(created);
    }

    @GetMapping(path = "/lab-orders/{orderId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<LabOrderView> order(@PathVariable String orderId) {
        return orders.find(orderId).map(ResponseEntity::ok).orElseGet(() -> ResponseEntity.notFound().build());
    }

    @PostMapping(path = "/lab-orders/{orderId}/submission", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<JsonNode> submit(@PathVariable String orderId) {
        LabOrderView order = orders.find(orderId).orElse(null);
        if (order == null) {
            return ResponseEntity.status(404).body(json.createObjectNode().put("error", "not_found"));
        }
        PatientView patient = patients.findPatient(order.patientId()).orElse(null);
        if (patient == null) {
            return ResponseEntity.status(404).body(json.createObjectNode().put("error", "not_found"));
        }
        ObjectNode body = json.createObjectNode();
        body.put("sourceOrganizationId", settings.getOrganizationId());
        body.put("destinationSystemKey", order.destinationSystemKey());
        body.put("externalRequestId", order.orderId());
        body.put("testCode", order.testCode());
        body.put("testDescription", order.testDescription());
        body.put("requestedAt", order.requestedAt());
        ObjectNode identity = body.putObject("patient");
        identity.put("identifierSystem", SyntheticSeed.PROPRIETARY_PATIENT_SYSTEM);
        identity.put("identifierValue", patient.patientId());
        identity.put("familyName", patient.familyName());
        identity.put("givenName", patient.givenName());
        identity.put("birthDate", patient.birthDate());
        identity.put("administrativeSex", patient.administrativeSex());
        try {
            JsonNode accepted = exchange.submit(body);
            orders.markSubmitted(
                    order.orderId(),
                    accepted.path("correlationId").asText(),
                    accepted.path("destination").path("orderId").asText(),
                    accepted.path("destination").path("organizationId").asText());
            log.info(
                    "mini_his_lab_order_submitted id={} correlation={}",
                    order.orderId(),
                    accepted.path("correlationId").asText());
            return ResponseEntity.ok(accepted);
        } catch (ExchangeGateway.ExchangeGatewayException ex) {
            orders.markFailed(order.orderId());
            log.info("mini_his_lab_order_submit_failed id={} error={}", order.orderId(), ex.code());
            return ResponseEntity.status(ex.status()).body(json.createObjectNode().put("error", ex.code()));
        }
    }

    @GetMapping(path = "/lab-orders/{orderId}/results", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<JsonNode> results(@PathVariable String orderId) {
        LabOrderView order = orders.find(orderId).orElse(null);
        if (order == null) {
            return ResponseEntity.status(404).body(json.createObjectNode().put("error", "not_found"));
        }
        if (order.correlationId() == null || order.correlationId().isBlank()) {
            return ResponseEntity.status(409).body(json.createObjectNode().put("error", "not_submitted"));
        }
        try {
            JsonNode report = exchange.report(order.orderId());
            log.info("mini_his_lab_results_read id={} correlation={}", order.orderId(), order.correlationId());
            return ResponseEntity.ok(report);
        } catch (ExchangeGateway.ExchangeGatewayException ex) {
            log.info("mini_his_lab_results_failed id={} error={}", order.orderId(), ex.code());
            return ResponseEntity.status(ex.status()).body(json.createObjectNode().put("error", ex.code()));
        }
    }

    @ExceptionHandler(org.springframework.http.converter.HttpMessageNotReadableException.class)
    public ResponseEntity<Map<String, String>> unreadable() {
        return ResponseEntity.badRequest().body(Map.of("error", "invalid_request"));
    }

    public record LabOrderRequest(
            String patientId,
            String destinationSystemKey,
            String testCode,
            String testDescription,
            String requestedAt) {
    }
}
