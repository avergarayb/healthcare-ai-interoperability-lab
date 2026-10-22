package lab.healthcare.fhir.exchange;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

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

import jakarta.servlet.http.HttpServletRequest;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.Map;

@RestController
public class ExchangeController {

    private static final Logger log = LoggerFactory.getLogger(ExchangeController.class);

    private final ExchangeService exchange;

    public ExchangeController(ExchangeService exchange) {
        this.exchange = exchange;
    }

    @PostMapping(path = "/api/exchange/v1/orders", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<ExchangeReceipt> submit(HttpServletRequest request, @RequestBody OrderBody body) {
        String caller = caller(request);
        ExchangeReceipt receipt = exchange.submit(caller, body.toSubmission());
        log.info("exchange_http_submit caller={} correlation={} state={}", caller, receipt.correlationId(), receipt.deliveryState());
        return ResponseEntity.status("duplicate".equals(receipt.deliveryState()) ? 200 : 201).body(receipt);
    }

    @GetMapping(path = "/api/exchange/v1/orders/{sourceOrderId}/report", produces = MediaType.APPLICATION_JSON_VALUE)
    public ExchangeReceipt report(HttpServletRequest request, @PathVariable String sourceOrderId) {
        String caller = caller(request);
        ExchangeReceipt receipt = exchange.report(caller, sourceOrderId);
        log.info("exchange_http_report caller={} correlation={}", caller, receipt.correlationId());
        return receipt;
    }

    @ExceptionHandler(ExchangeException.class)
    public ResponseEntity<Map<String, String>> failed(ExchangeException ex) {
        Map<String, String> body = new LinkedHashMap<>();
        body.put("error", ex.code());
        if (ex.correlationId() != null) {
            body.put("correlationId", ex.correlationId());
        }
        return ResponseEntity.status(ex.status()).body(body);
    }

    private static String caller(HttpServletRequest request) {
        Object caller = request.getAttribute(ExchangeSecurityConfiguration.CALLER_ATTRIBUTE);
        if (!(caller instanceof String system) || system.isBlank()) {
            throw ExchangeException.forbidden();
        }
        return system;
    }

    @JsonIgnoreProperties(ignoreUnknown = false)
    public record OrderBody(
            String sourceOrganizationId,
            String destinationSystemKey,
            String externalRequestId,
            String testCode,
            String testDescription,
            OffsetDateTime requestedAt,
            PatientBody patient) {

        OrderSubmission toSubmission() {
            if (patient == null) {
                throw ExchangeException.invalidRequest();
            }
            return new OrderSubmission(
                    sourceOrganizationId,
                    destinationSystemKey,
                    externalRequestId,
                    testCode,
                    testDescription,
                    requestedAt,
                    new PatientIdentity(
                            patient.identifierSystem(),
                            patient.identifierValue(),
                            patient.familyName(),
                            patient.givenName(),
                            patient.birthDate(),
                            patient.administrativeSex()));
        }
    }

    public record PatientBody(
            String identifierSystem,
            String identifierValue,
            String familyName,
            String givenName,
            LocalDate birthDate,
            String administrativeSex) {
    }
}
