package lab.healthcare.minilis;

import jakarta.validation.Valid;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;
import java.util.List;
import java.util.Map;

@RestController
public class MiniLisController {

    private static final Logger log = LoggerFactory.getLogger(MiniLisController.class);
    private static final int DEFAULT_LIMIT = 50;
    private static final int MAX_LIMIT = 100;

    private final LaboratoryRecordService records;

    public MiniLisController(LaboratoryRecordService records) {
        this.records = records;
    }

    @GetMapping(path = "/health", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, String> health() {
        return Map.of("status", "up");
    }

    @PostMapping(path = "/patients", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<ExternalPatient> registerPatient(@Valid @RequestBody PatientRequest request) {
        ExternalPatient patient = records.registerPatient(new NewPatient(
                request.organizationId(),
                request.externalId(),
                request.familyName(),
                request.givenName(),
                request.birthDate(),
                request.administrativeSex()));
        log.info("mini_lis_patient_registered id={}", patient.patientId());
        return ResponseEntity.created(URI.create("/patients/" + patient.patientId())).body(patient);
    }

    @GetMapping(path = "/patients", produces = MediaType.APPLICATION_JSON_VALUE)
    public Object patients(
            @RequestParam(required = false) String organizationId,
            @RequestParam(required = false) String externalId,
            @RequestParam(required = false) Integer limit) {
        if (organizationId == null && externalId == null) {
            Integer bounded = bound(limit);
            if (bounded == null) {
                return invalidLimit();
            }
            return records.listPatients(bounded);
        }
        if (organizationId == null || externalId == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "invalid_request"));
        }
        return records.searchPatients(organizationId, externalId);
    }

    @GetMapping(path = "/patients/{patientId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ExternalPatient patient(@PathVariable String patientId) {
        return records.patient(patientId);
    }

    @PostMapping(path = "/orders", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<LabOrder> createOrder(@Valid @RequestBody OrderRequest request) {
        LabOrder order = records.createOrder(new NewOrder(
                request.patientId(),
                request.requestingOrganizationId(),
                request.externalRequestId(),
                request.testCode(),
                request.testDescription(),
                request.requestedAt()));
        log.info("mini_lis_order_created id={} patient={}", order.orderId(), order.patientId());
        return ResponseEntity.created(URI.create("/orders/" + order.orderId())).body(order);
    }

    @GetMapping(path = "/orders", produces = MediaType.APPLICATION_JSON_VALUE)
    public Object orders(
            @RequestParam(required = false) Integer limit,
            @RequestParam(required = false) String requestingOrganizationId,
            @RequestParam(required = false) String externalRequestId) {
        if (requestingOrganizationId != null || externalRequestId != null) {
            if (requestingOrganizationId == null || externalRequestId == null) {
                return ResponseEntity.badRequest().body(Map.of("error", "invalid_request"));
            }
            return records.orderByExternalRequest(requestingOrganizationId, externalRequestId);
        }
        Integer bounded = bound(limit);
        if (bounded == null) {
            return invalidLimit();
        }
        return records.listOrders(bounded);
    }

    @GetMapping(path = "/orders/{orderId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public LabOrder order(@PathVariable String orderId) {
        return records.order(orderId);
    }

    @GetMapping(path = "/patients/{patientId}/orders", produces = MediaType.APPLICATION_JSON_VALUE)
    public List<LabOrder> ordersForPatient(@PathVariable String patientId) {
        return records.ordersForPatient(patientId);
    }

    @PostMapping(path = "/orders/{orderId}/results", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<LabResult> recordResult(@PathVariable String orderId, @Valid @RequestBody ResultRequest request) {
        LabResult result = records.recordResult(new NewResult(
                orderId,
                request.externalResultId(),
                request.testCode(),
                request.value(),
                request.unit(),
                request.referenceRange(),
                request.resultedAt(),
                request.status()));
        log.info("mini_lis_result_recorded id={} order={}", result.resultId(), result.orderId());
        return ResponseEntity.created(URI.create("/orders/" + orderId + "/results")).body(result);
    }

    @GetMapping(path = "/results/{resultId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public LabResult result(@PathVariable String resultId) {
        return records.result(resultId);
    }

    @GetMapping(path = "/orders/{orderId}/results", produces = MediaType.APPLICATION_JSON_VALUE)
    public List<LabResult> resultsForOrder(@PathVariable String orderId) {
        return records.resultsForOrder(orderId);
    }

    @GetMapping(path = "/patients/{patientId}/results", produces = MediaType.APPLICATION_JSON_VALUE)
    public List<LabResult> resultsForPatient(@PathVariable String patientId) {
        return records.resultsForPatient(patientId);
    }

    @PostMapping(path = "/orders/{orderId}/completion", produces = MediaType.APPLICATION_JSON_VALUE)
    public LabOrder complete(@PathVariable String orderId) {
        LabOrder order = records.complete(orderId);
        log.info("mini_lis_order_completed id={}", order.orderId());
        return order;
    }

    @PostMapping(path = "/orders/{orderId}/cancellation", produces = MediaType.APPLICATION_JSON_VALUE)
    public LabOrder cancel(@PathVariable String orderId) {
        LabOrder order = records.cancel(orderId);
        log.info("mini_lis_order_cancelled id={}", order.orderId());
        return order;
    }

    private static Integer bound(Integer limit) {
        if (limit == null) {
            return DEFAULT_LIMIT;
        }
        if (limit < 1 || limit > MAX_LIMIT) {
            return null;
        }
        return limit;
    }

    private static ResponseEntity<Map<String, String>> invalidLimit() {
        return ResponseEntity.badRequest().body(Map.of("error", "invalid_request"));
    }
}
