package lab.healthcare.fhir.exchange;

import lab.healthcare.fhir.clinicalread.minilis.MiniLisFhirMapping;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import jakarta.annotation.PreDestroy;

import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Pattern;

/**
 * HL7 v2.5.1 connector for Mini LIS. Orders leave as OML^O21. Results arrive
 * as ORU^R01 and are stored as FHIR. REST remains the default connector.
 */
public final class MiniLisHl7ExchangeConnector implements OrderDestination, ResultSource {

    private static final Logger log = LoggerFactory.getLogger(MiniLisHl7ExchangeConnector.class);
    private static final Pattern ID = Pattern.compile("[A-Za-z0-9\\-.]{1,64}");

    private final ExchangeProperties.Hl7 peer;
    private final String host;
    private final int port;
    private final String secret;
    private final Duration connectTimeout;
    private final Duration readTimeout;
    private final ExchangeStore store;
    private final ObjectMapper json;
    private final MiniLisFhirMapping mapping;
    private final Hl7ExchangeCodec codec = new Hl7ExchangeCodec();
    private final ThreadLocal<PatientIdentity> staged = new ThreadLocal<>();
    private ServerSocket listener;
    private ExecutorService workers;
    private volatile boolean running;

    public MiniLisHl7ExchangeConnector(
            ExchangeProperties.Hl7 peer,
            String host,
            int port,
            String secret,
            Duration connectTimeout,
            Duration readTimeout,
            ExchangeStore store,
            ObjectMapper json) {
        if (!MllpSession.loopback(host)) {
            throw new IllegalArgumentException("Mini LIS HL7 host must be a loopback address");
        }
        this.peer = peer;
        this.host = host;
        this.port = port;
        this.secret = secret == null ? "" : secret;
        this.connectTimeout = connectTimeout;
        this.readTimeout = readTimeout;
        this.store = store;
        this.json = json;
        this.mapping = new MiniLisFhirMapping(json);
        startListener();
    }

    @Override
    public String systemKey() {
        return "mini-lis";
    }

    @Override
    public boolean embedsPatientInOrder() {
        return true;
    }

    @Override
    public String resolvePatient(String requestingOrganizationId, PatientIdentity identity) {
        staged.set(identity);
        return identity.identifierValue();
    }

    @Override
    public AcceptedOrder accept(DestinationCommand command) {
        PatientIdentity patient = staged.get();
        staged.remove();
        if (patient == null || secret.isBlank()) {
            throw ExchangeException.unavailable();
        }
        if (forbidden(command.testSystem())) {
            throw ExchangeException.invalidRequest();
        }
        String controlId = "MSG-" + UUID.randomUUID().toString().replace("-", "").substring(0, 16).toUpperCase(Locale.ROOT);
        String er7 = codec.oml(peer, controlId, secret, command, patient);
        Hl7ExchangeCodec.Ack ack;
        try {
            ack = codec.ack(MllpSession.transact(host, port, er7, connectTimeout, readTimeout));
        } catch (Exception ex) {
            log.info("hl7_oml_failed control={} error=unavailable", controlId);
            throw ExchangeException.unavailable();
        }
        if (!"AA".equals(ack.code())) {
            log.info("hl7_oml_rejected control={} ack={}", controlId, ack.code());
            if ("organization_forbidden".equals(ack.detail())) {
                throw ExchangeException.forbidden();
            }
            if ("AE".equals(ack.code())) {
                throw ExchangeException.rejected();
            }
            throw ExchangeException.unavailable();
        }
        String orderId = Hl7ExchangeCodec.token(ack.detail(), "order");
        String patientId = Hl7ExchangeCodec.token(ack.detail(), "patient");
        if (!ID.matcher(orderId).matches() || !ID.matcher(patientId).matches()) {
            throw ExchangeException.unavailable();
        }
        boolean duplicate = "true".equals(Hl7ExchangeCodec.token(ack.detail(), "duplicate"));
        log.info("hl7_oml_accepted control={} order={} duplicate={}", controlId, orderId, duplicate);
        return new AcceptedOrder(orderId, duplicate, patientId);
    }

    @Override
    public DestinationReport read(String destinationOrderId) {
        List<JsonNode> observations = new ArrayList<>();
        ObjectNode order = null;
        for (String stored : store.hl7Observations(destinationOrderId)) {
            try {
                JsonNode result = json.readTree(stored);
                observations.add(mapping.observation(result));
                if (order == null) {
                    order = json.createObjectNode();
                    order.put("orderId", destinationOrderId);
                    order.put("patientId", result.path("patientId").asText());
                    order.put("requestingOrganizationId", result.path("organizationId").asText());
                    order.put("externalRequestId", result.path("externalRequestId").asText());
                    order.put("testCode", result.path("testCode").asText());
                    order.put("testDescription", result.path("testDescription").asText("Laboratory test"));
                    order.put("requestedAt", result.path("requestedAt").asText());
                    order.put("status", result.path("orderStatus").asText("IN_PROGRESS"));
                }
            } catch (Exception ex) {
                throw ExchangeException.unavailable();
            }
        }
        if (order == null) {
            ObjectNode report = json.createObjectNode();
            report.put("resourceType", "DiagnosticReport");
            report.put("id", destinationOrderId);
            report.put("status", "registered");
            report.putArray("result");
            ObjectNode serviceRequest = json.createObjectNode();
            serviceRequest.put("resourceType", "ServiceRequest");
            serviceRequest.put("id", destinationOrderId);
            serviceRequest.put("status", "active");
            serviceRequest.put("intent", "order");
            return new DestinationReport(serviceRequest, report, List.of());
        }
        return new DestinationReport(
                mapping.serviceRequest(order),
                mapping.diagnosticReport(order, json.valueToTree(observationsSource(observations, order))),
                observations);
    }

    public int listenPort() {
        return listener == null ? -1 : listener.getLocalPort();
    }

    @PreDestroy
    public void stop() {
        running = false;
        if (listener != null) {
            try {
                listener.close();
            } catch (Exception ignored) {
                // The process is stopping.
            }
        }
        if (workers != null) {
            workers.shutdownNow();
        }
    }

    private void startListener() {
        try {
            listener = MllpSession.listen(peer.getListenPort());
            running = true;
            workers = Executors.newCachedThreadPool(task -> {
                Thread thread = new Thread(task, "exchange-mllp");
                thread.setDaemon(true);
                return thread;
            });
            Thread acceptor = new Thread(this::acceptLoop, "exchange-mllp-accept");
            acceptor.setDaemon(true);
            acceptor.start();
            log.info("hl7_result_listener_started port={}", listener.getLocalPort());
        } catch (Exception ex) {
            throw new IllegalStateException("HL7 result listener did not start");
        }
    }

    private void acceptLoop() {
        while (running) {
            try {
                Socket socket = listener.accept();
                workers.execute(() -> handle(socket));
            } catch (Exception ex) {
                if (running) {
                    log.info("hl7_result_accept_failed");
                }
            }
        }
    }

    private void handle(Socket socket) {
        try (socket) {
            socket.setSoTimeout((int) readTimeout.toMillis());
            String er7 = MllpSession.read(socket.getInputStream());
            String ack = acceptOru(er7);
            MllpSession.write(socket.getOutputStream(), ack);
        } catch (Exception ex) {
            log.info("hl7_result_session_failed");
        }
    }

    private String acceptOru(String er7) {
        Hl7ExchangeCodec.Oru oru = codec.oru(er7);
        if (oru == null || !ID.matcher(oru.controlId()).matches()) {
            log.info("hl7_oru_rejected error=invalid_request");
            return codec.ackMessage(peer, "R01", "AR", "UNKNOWN", "invalid_request");
        }
        if (!peerMatches(oru)) {
            log.info("hl7_oru_rejected control={} error=unauthorized", oru.controlId());
            return codec.ackMessage(peer, "R01", "AR", oru.controlId(), "unauthorized");
        }
        if (oru.forbiddenCodeSystem()) {
            log.info("hl7_oru_rejected control={} error=invalid_request", oru.controlId());
            return codec.ackMessage(peer, "R01", "AE", oru.controlId(), "invalid_request");
        }
        OrderCorrelation correlation = store.findByDestinationOrder("mini-lis", oru.fillerOrderId()).orElse(null);
        String status = domainResult(oru.resultFlag());
        String orderStatus = domainOrder(oru.orderStatus());
        var resultedAt = Hl7ExchangeCodec.parseTime(oru.resultedAt());
        if (correlation == null
                || correlation.destinationPatientId() == null
                || !correlation.sourceOrderId().equals(oru.placerOrderId())
                || !correlation.sourceOrganizationId().equals(oru.organizationId())
                || !correlation.sourceOrganizationId().equals(oru.orderingOrganizationId())
                || !correlation.patientIdentifierValue().equals(oru.externalPatientId())
                || !correlation.testCode().equals(oru.testCode())
                || !ID.matcher(oru.externalResultId()).matches()
                || oru.value().isBlank()
                || status.isBlank()
                || resultedAt == null) {
            log.info("hl7_oru_rejected control={} error=invalid_request", oru.controlId());
            return codec.ackMessage(peer, "R01", "AE", oru.controlId(), "invalid_request");
        }
        ObjectNode body = json.createObjectNode();
        body.put("resultId", oru.controlId());
        body.put("orderId", oru.fillerOrderId());
        body.put("patientId", correlation.destinationPatientId());
        body.put("organizationId", correlation.sourceOrganizationId());
        body.put("externalRequestId", correlation.sourceOrderId());
        body.put("externalResultId", oru.externalResultId());
        body.put("testCode", oru.testCode());
        body.put("testDescription", correlation.testDescription());
        body.put("value", oru.value());
        if (!oru.unit().isBlank()) {
            body.put("unit", oru.unit());
        }
        if (!oru.referenceRange().isBlank()) {
            body.put("referenceRange", oru.referenceRange());
        }
        body.put("resultedAt", resultedAt.toString());
        body.put("status", status);
        body.put("requestedAt", correlation.requestedAt().toString());
        body.put("orderStatus", orderStatus.isBlank() ? "IN_PROGRESS" : orderStatus);
        boolean stored = store.saveHl7Observation(
                oru.controlId(), oru.fillerOrderId(), correlation.sourceOrderId(), oru.externalResultId(), body.toString());
        String detail = "order=" + oru.fillerOrderId() + "&result=" + oru.externalResultId() + "&duplicate=" + !stored;
        log.info("hl7_oru_accepted control={} order={} duplicate={}", oru.controlId(), oru.fillerOrderId(), !stored);
        return codec.ackMessage(peer, "R01", "AA", oru.controlId(), detail);
    }

    private boolean peerMatches(Hl7ExchangeCodec.Oru oru) {
        if (secret.isBlank() || oru.security().isBlank()) {
            return false;
        }
        boolean secretMatches = MessageDigest.isEqual(
                secret.getBytes(StandardCharsets.UTF_8), oru.security().getBytes(StandardCharsets.UTF_8));
        return secretMatches
                && peer.getReceivingApplication().equals(oru.sendingApplication())
                && peer.getReceivingFacility().equals(oru.sendingFacility())
                && peer.getSendingApplication().equals(oru.receivingApplication())
                && peer.getSendingFacility().equals(oru.receivingFacility());
    }

    private static boolean forbidden(String system) {
        String lower = system == null ? "" : system.toLowerCase(Locale.ROOT);
        return lower.contains("loinc") || lower.contains("ucum");
    }

    private static String domainResult(String flag) {
        return switch (flag) {
            case "P" -> "PRELIMINARY";
            case "F" -> "FINAL";
            case "X" -> "CANCELLED";
            default -> "";
        };
    }

    private static String domainOrder(String status) {
        return switch (status) {
            case "SC" -> "ORDERED";
            case "IP" -> "IN_PROGRESS";
            case "CM" -> "COMPLETED";
            case "CA" -> "CANCELLED";
            default -> "";
        };
    }

    private List<ObjectNode> observationsSource(List<JsonNode> observations, ObjectNode order) {
        List<ObjectNode> source = new ArrayList<>();
        for (String stored : store.hl7Observations(order.path("orderId").asText())) {
            try {
                source.add((ObjectNode) json.readTree(stored));
            } catch (Exception ex) {
                throw ExchangeException.unavailable();
            }
        }
        return source;
    }
}
