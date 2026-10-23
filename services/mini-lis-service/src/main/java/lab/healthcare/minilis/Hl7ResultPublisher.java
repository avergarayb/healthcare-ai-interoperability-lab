package lab.healthcare.minilis;

import ca.uhn.hl7v2.util.Terser;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

import java.nio.charset.StandardCharsets;

/**
 * Publishes one ORU^R01 after a result commits. The REST write remains
 * successful when the peer does not answer. AA means the interoperability
 * service stored the message, not that a clinician reviewed it.
 */
@Component
public class Hl7ResultPublisher {

    private static final Logger log = LoggerFactory.getLogger(Hl7ResultPublisher.class);

    private final LaboratoryRecordService records;
    private final Hl7Properties properties;
    private final Hl7Messages messages = new Hl7Messages();
    private volatile String host;
    private volatile int port;

    public Hl7ResultPublisher(LaboratoryRecordService records, Hl7Properties properties) {
        this.records = records;
        this.properties = properties;
        this.host = properties.getOutboundHost();
        this.port = properties.getOutboundPort();
    }

    public void configurePeer(String host, int port) {
        if (!BindPolicy.isLoopback(host) || port < 1 || port > 65535) {
            throw MiniLisException.invalidRequest();
        }
        this.host = host;
        this.port = port;
    }

    public int peerPort() {
        return port;
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onResult(LabResultRecorded event) {
        try {
            publish(event.resultId());
        } catch (RuntimeException ex) {
            log.info("hl7_oru_failed result={} error=unavailable", event.resultId());
        }
    }

    public String publish(String resultId) {
        if (port < 1) {
            return "not_configured";
        }
        if (properties.getSharedSecret().isBlank()) {
            log.info("hl7_oru_failed result={} error=unauthorized", resultId);
            return "unauthorized";
        }
        LabResult result = records.result(resultId);
        LabOrder order = records.order(result.orderId());
        ExternalPatient patient = records.patient(result.patientId());
        String er7 = messages.oru(new Hl7Messages.OruPayload(
                properties.getReceivingApplication(),
                properties.getReceivingFacility(),
                properties.getSendingApplication(),
                properties.getSendingFacility(),
                properties.getSharedSecret(),
                result.resultId(),
                patient.organizationId(),
                patient.externalId(),
                patient.familyName(),
                patient.givenName(),
                patient.birthDate(),
                patient.administrativeSex(),
                order.externalRequestId(),
                order.orderId(),
                order.status().name(),
                result.testCode(),
                order.testDescription(),
                order.requestedAt(),
                result.externalResultId(),
                result.value(),
                result.unit(),
                result.referenceRange(),
                result.status().name(),
                result.resultedAt()));
        try {
            String ack = MllpExchange.transact(host, port, er7, properties.getConnectTimeout(), properties.getReadTimeout());
            Hl7Messages.ParsedMessage parsed = messages.parse(ack);
            String code = parsed == null ? "AR" : Hl7Messages.value(parsed.terser(), "/MSA-1");
            String detail = parsed == null ? "invalid_request" : safeDetail(parsed.terser());
            log.info("hl7_oru_sent result={} ack={} detail={}", result.resultId(), code, detail);
            return code;
        } catch (Exception ex) {
            log.info("hl7_oru_failed result={} error=unavailable", result.resultId());
            return "unavailable";
        }
    }

    private static String safeDetail(Terser terser) {
        String detail = Hl7Messages.value(terser, "/MSA-3");
        if (detail.matches("[A-Za-z0-9\\-.=&]{0,200}")) {
            return detail;
        }
        return "unrecognized";
    }
}
