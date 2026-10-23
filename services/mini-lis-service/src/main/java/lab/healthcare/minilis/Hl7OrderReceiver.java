package lab.healthcare.minilis;

import ca.uhn.hl7v2.util.Terser;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.regex.Pattern;

/**
 * Accepts one OML^O21. A stored order is answered with ORL^O22. A rejection
 * stays an ACK. The domain write goes through {@link LaboratoryRecordService}.
 * MSH-4 identifies the sending system only after the shared secret matches.
 * The requesting organization is ORC-21-10.
 */
@Component
public class Hl7OrderReceiver {

    private static final Logger log = LoggerFactory.getLogger(Hl7OrderReceiver.class);
    private static final Pattern ID = Pattern.compile("[A-Za-z0-9\\-.]{1,64}");

    private final LaboratoryRecordService records;
    private final Hl7Properties properties;
    private final Hl7Messages messages = new Hl7Messages();

    public Hl7OrderReceiver(LaboratoryRecordService records, Hl7Properties properties) {
        this.records = records;
        this.properties = properties;
    }

    public String acknowledge(String er7) {
        Hl7Messages.ParsedMessage parsed = messages.parse(er7);
        if (parsed == null || !"OML".equals(parsed.type()) || !"O21".equals(parsed.event())) {
            String controlId = parsed == null ? "UNKNOWN" : Hl7Messages.value(parsed.terser(), "/MSH-10");
            String code = parsed == null ? "invalid_request" : "unsupported_message";
            log.info("hl7_oml_rejected error={}", code);
            return messages.ack(properties.getReceivingApplication(), properties.getReceivingFacility(), "O21", "AR", controlId, code);
        }
        Terser terser = parsed.terser();
        String controlId = Hl7Messages.value(terser, "/MSH-10");
        if (!ID.matcher(controlId).matches() || !Hl7Messages.VERSION.equals(Hl7Messages.value(terser, "/MSH-12"))) {
            log.info("hl7_oml_rejected error=invalid_request");
            return messages.ack(properties.getReceivingApplication(), properties.getReceivingFacility(), "O21", "AR", safe(controlId), "invalid_request");
        }
        if (!peerMatches(terser)) {
            log.info("hl7_oml_rejected control={} error=unauthorized", controlId);
            return messages.ack(properties.getReceivingApplication(), properties.getReceivingFacility(), "O21", "AR", controlId, "unauthorized");
        }
        String organizationId = Hl7Messages.value(terser, "/ORDER/ORC-21-10");
        if (!properties.allowedOrganizationList().contains(organizationId) || !organizationId.equals(Hl7Messages.value(terser, "/PATIENT/PID-3-4"))) {
            Hl7Ack rejected = records.rememberRejection(controlId, null, "AE", "organization_forbidden");
            log.info("hl7_oml_rejected control={} error={}", controlId, rejected.detail());
            return messages.ack(properties.getReceivingApplication(), properties.getReceivingFacility(), "O21", rejected.code(), controlId, rejected.detail());
        }
        OmlOrder order = order(terser, controlId, organizationId);
        if (order == null || Hl7Messages.forbiddenCodeSystem(Hl7Messages.value(terser, "/ORDER/OBSERVATION_REQUEST/OBR-4-3"))) {
            Hl7Ack rejected = records.rememberRejection(controlId, order == null ? null : order.placerOrderId(), "AE", "invalid_request");
            log.info("hl7_oml_rejected control={} error=invalid_request", controlId);
            return messages.ack(properties.getReceivingApplication(), properties.getReceivingFacility(), "O21", rejected.code(), controlId, rejected.detail());
        }
        try {
            Hl7Ack ack = records.acceptOml(order);
            log.info("hl7_oml_accepted control={} order={} duplicate={}", controlId, ack.fillerOrderId(), ack.duplicate());
            return messages.orderResponse(
                    properties.getReceivingApplication(),
                    properties.getReceivingFacility(),
                    properties.getSendingApplication(),
                    properties.getSendingFacility(),
                    controlId,
                    order.placerOrderId(),
                    ack);
        } catch (MiniLisException ex) {
            String detail = "invalid_request".equals(ex.code()) || "invalid_transition".equals(ex.code()) || "not_found".equals(ex.code())
                    ? ex.code()
                    : "invalid_request";
            Hl7Ack rejected = records.rememberRejection(controlId, order.placerOrderId(), "AE", detail);
            log.info("hl7_oml_rejected control={} error={}", controlId, detail);
            return messages.ack(properties.getReceivingApplication(), properties.getReceivingFacility(), "O21", rejected.code(), controlId, rejected.detail());
        }
    }

    private boolean peerMatches(Terser terser) {
        String secret = properties.getSharedSecret();
        String presented = Hl7Messages.value(terser, "/MSH-8");
        if (secret.isBlank() || presented.isBlank()) {
            return false;
        }
        boolean secretMatches = MessageDigest.isEqual(secret.getBytes(StandardCharsets.UTF_8), presented.getBytes(StandardCharsets.UTF_8));
        return secretMatches
                && properties.getSendingApplication().equals(Hl7Messages.value(terser, "/MSH-3"))
                && properties.getSendingFacility().equals(Hl7Messages.value(terser, "/MSH-4"))
                && properties.getReceivingApplication().equals(Hl7Messages.value(terser, "/MSH-5"))
                && properties.getReceivingFacility().equals(Hl7Messages.value(terser, "/MSH-6"));
    }

    private static OmlOrder order(Terser terser, String controlId, String organizationId) {
        String externalId = Hl7Messages.value(terser, "/PATIENT/PID-3-1");
        String family = Hl7Messages.value(terser, "/PATIENT/PID-5-1");
        String given = Hl7Messages.value(terser, "/PATIENT/PID-5-2");
        LocalDate birthDate = Hl7Messages.parseDate(Hl7Messages.value(terser, "/PATIENT/PID-7"));
        String sex = Hl7Messages.administrativeSex(Hl7Messages.value(terser, "/PATIENT/PID-8"));
        String placer = Hl7Messages.value(terser, "/ORDER/ORC-2-1");
        String code = Hl7Messages.value(terser, "/ORDER/OBSERVATION_REQUEST/OBR-4-1");
        String description = Hl7Messages.value(terser, "/ORDER/OBSERVATION_REQUEST/OBR-4-2");
        OffsetDateTime requestedAt = Hl7Messages.parseTime(Hl7Messages.value(terser, "/ORDER/OBSERVATION_REQUEST/OBR-7"));
        if (!ID.matcher(externalId).matches() || !ID.matcher(placer).matches() || !ID.matcher(code).matches()
                || family.isBlank() || given.isBlank() || birthDate == null || sex.isBlank()
                || description.isBlank() || description.length() > 200 || requestedAt == null
                || !"NW".equals(Hl7Messages.value(terser, "/ORDER/ORC-1"))) {
            return null;
        }
        return new OmlOrder(controlId, organizationId, externalId, family, given, birthDate, sex, placer, code, description, requestedAt);
    }

    private static String safe(String controlId) {
        return ID.matcher(controlId == null ? "" : controlId).matches() ? controlId : "UNKNOWN";
    }
}
