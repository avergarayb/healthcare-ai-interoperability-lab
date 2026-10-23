package lab.healthcare.minilis;

import ca.uhn.hl7v2.DefaultHapiContext;
import ca.uhn.hl7v2.HapiContext;
import ca.uhn.hl7v2.model.Message;
import ca.uhn.hl7v2.parser.Parser;
import ca.uhn.hl7v2.util.Terser;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.Locale;

/**
 * HL7 v2.5.1 laboratory profile. OML^O21 carries an order, ORU^R01 carries one
 * result, and ACK confirms that the message was accepted for storage. AA is
 * not confirmation that the assay is complete.
 */
public final class Hl7Messages {

    public static final String VERSION = "2.5.1";
    public static final String LIS_TEST_SYSTEM = "https://lab.local/mini-lis/test";

    static {
        if (System.getProperty("hapi.home") == null) {
            System.setProperty("hapi.home", System.getProperty("java.io.tmpdir"));
        }
    }

    private static final DateTimeFormatter HL7_TIME = DateTimeFormatter.ofPattern("yyyyMMddHHmmssZ");
    private static final DateTimeFormatter HL7_DATE = DateTimeFormatter.ofPattern("yyyyMMdd");

    private final HapiContext context;
    private final Parser parser;

    public Hl7Messages() {
        this.context = new DefaultHapiContext();
        this.context.getParserConfiguration().setValidating(false);
        this.parser = this.context.getPipeParser();
    }

    public synchronized ParsedMessage parse(String er7) {
        try {
            Message message = parser.parse(er7);
            Terser terser = new Terser(message);
            String type = value(terser, "/MSH-9-1");
            String event = value(terser, "/MSH-9-2");
            return new ParsedMessage(type, event, terser, message);
        } catch (RuntimeException | ca.uhn.hl7v2.HL7Exception ex) {
            return null;
        }
    }

    public synchronized String orderResponse(
            String sendingApplication,
            String sendingFacility,
            String receivingApplication,
            String receivingFacility,
            String controlId,
            String placerOrderId,
            Hl7Ack ack) {
        try {
            ca.uhn.hl7v2.model.v251.message.ORL_O22 message = new ca.uhn.hl7v2.model.v251.message.ORL_O22();
            message.initQuickstart("ORL", "O22", "P");
            Terser terser = new Terser(message);
            terser.set("/MSH-3", sendingApplication);
            terser.set("/MSH-4", sendingFacility);
            terser.set("/MSH-5", receivingApplication);
            terser.set("/MSH-6", receivingFacility);
            terser.set("/MSH-10", "ORL-" + controlId);
            terser.set("/MSH-11", "P");
            terser.set("/MSH-12", VERSION);
            terser.set("/MSH-18", "UNICODE UTF-8");
            terser.set("/MSA-1", "AA");
            terser.set("/MSA-2", controlId);
            terser.set("/MSA-3", ack.duplicate() ? "duplicate" : "");
            terser.set("/RESPONSE/PATIENT/PID-3-1", ack.patientId());
            terser.set("/RESPONSE/PATIENT/ORDER/ORC-1", "OK");
            terser.set("/RESPONSE/PATIENT/ORDER/ORC-2-1", placerOrderId);
            terser.set("/RESPONSE/PATIENT/ORDER/ORC-3-1", ack.fillerOrderId());
            return parser.encode(message);
        } catch (Exception ex) {
            throw new IllegalStateException("ORL could not be built");
        }
    }

    public synchronized String ack(String sendingApplication, String sendingFacility, String trigger, String code, String controlId, String detail) {
        try {
            Message ack = parser.parse(parser.encode(newAck(trigger)));
            Terser terser = new Terser(ack);
            terser.set("/MSH-3", sendingApplication);
            terser.set("/MSH-4", sendingFacility);
            terser.set("/MSH-9-1", "ACK");
            terser.set("/MSH-9-2", trigger);
            terser.set("/MSH-11", "P");
            terser.set("/MSH-12", VERSION);
            terser.set("/MSH-18", "UNICODE UTF-8");
            terser.set("/MSA-1", code);
            terser.set("/MSA-2", controlId == null || controlId.isBlank() ? "UNKNOWN" : controlId);
            terser.set("/MSA-3", detail == null ? "" : detail);
            return parser.encode(ack);
        } catch (Exception ex) {
            return "MSH|^~\\&|" + sendingApplication + "|" + sendingFacility + "|||000000||ACK^" + trigger
                    + "|UNKNOWN|P|2.5.1\rMSA|AR|UNKNOWN|invalid_request\r";
        }
    }

    public synchronized String oml(OmlPayload payload) {
        try {
            ca.uhn.hl7v2.model.v251.message.OML_O21 message = new ca.uhn.hl7v2.model.v251.message.OML_O21();
            message.initQuickstart("OML", "O21", "P");
            Terser terser = new Terser(message);
            terser.set("/MSH-3", payload.sendingApplication());
            terser.set("/MSH-4", payload.sendingFacility());
            terser.set("/MSH-5", payload.receivingApplication());
            terser.set("/MSH-6", payload.receivingFacility());
            terser.set("/MSH-8", payload.security());
            terser.set("/MSH-9-1", "OML");
            terser.set("/MSH-9-2", "O21");
            terser.set("/MSH-10", payload.messageControlId());
            terser.set("/MSH-11", "P");
            terser.set("/MSH-12", VERSION);
            terser.set("/MSH-18", "UNICODE UTF-8");
            setPatient(terser, "/PATIENT/PID", payload.organizationId(), payload.externalPatientId(), payload.familyName(), payload.givenName(), payload.birthDate(), payload.administrativeSex());
            terser.set("/ORDER/ORC-1", "NW");
            terser.set("/ORDER/ORC-2-1", payload.placerOrderId());
            terser.set("/ORDER/ORC-21-10", payload.organizationId());
            terser.set("/ORDER/OBSERVATION_REQUEST/OBR-1", "1");
            terser.set("/ORDER/OBSERVATION_REQUEST/OBR-2-1", payload.placerOrderId());
            terser.set("/ORDER/OBSERVATION_REQUEST/OBR-4-1", payload.testCode());
            terser.set("/ORDER/OBSERVATION_REQUEST/OBR-4-2", payload.testDescription());
            terser.set("/ORDER/OBSERVATION_REQUEST/OBR-4-3", payload.testSystem());
            terser.set("/ORDER/OBSERVATION_REQUEST/OBR-7", hl7Time(payload.requestedAt()));
            return parser.encode(message);
        } catch (Exception ex) {
            throw new IllegalStateException("OML could not be built");
        }
    }

    public synchronized String oru(OruPayload payload) {
        try {
            Message message = parser.parse(parser.encode(newOru()));
            Terser terser = new Terser(message);
            terser.set("/MSH-3", payload.sendingApplication());
            terser.set("/MSH-4", payload.sendingFacility());
            terser.set("/MSH-5", payload.receivingApplication());
            terser.set("/MSH-6", payload.receivingFacility());
            terser.set("/MSH-8", payload.security());
            terser.set("/MSH-9-1", "ORU");
            terser.set("/MSH-9-2", "R01");
            terser.set("/MSH-10", payload.messageControlId());
            terser.set("/MSH-11", "P");
            terser.set("/MSH-12", VERSION);
            terser.set("/MSH-18", "UNICODE UTF-8");
            setPatient(terser, "/PATIENT_RESULT/PATIENT/PID", payload.organizationId(), payload.externalPatientId(), payload.familyName(), payload.givenName(), payload.birthDate(), payload.administrativeSex());
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/ORC-1", "RE");
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/ORC-2-1", payload.placerOrderId());
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/ORC-3-1", payload.fillerOrderId());
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/ORC-5", orderStatus(payload.orderStatus()));
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/ORC-21-10", payload.organizationId());
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBR-1", "1");
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBR-2-1", payload.placerOrderId());
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBR-3-1", payload.fillerOrderId());
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBR-4-1", payload.testCode());
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBR-4-2", payload.testDescription());
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBR-4-3", LIS_TEST_SYSTEM);
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBR-7", hl7Time(payload.requestedAt()));
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBR-25", resultFlag(payload.resultStatus()));
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-1", "1");
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-2", numeric(payload.value()) ? "NM" : "ST");
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-3-1", payload.testCode());
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-3-2", payload.testDescription());
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-3-3", LIS_TEST_SYSTEM);
            // v2.5.1 reserves OBX-21. This profile uses OBX-4 for the external result id.
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-4", payload.externalResultId());
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-5", payload.value());
            if (payload.unit() != null && !payload.unit().isBlank()) {
                terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-6-1", payload.unit());
            }
            if (payload.referenceRange() != null && !payload.referenceRange().isBlank()) {
                terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-7", payload.referenceRange());
            }
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-11", resultFlag(payload.resultStatus()));
            terser.set("/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-14", hl7Time(payload.resultedAt()));
            return parser.encode(message);
        } catch (Exception ex) {
            throw new IllegalStateException("ORU could not be built");
        }
    }

    private static void setPatient(Terser terser, String prefix, String organizationId, String externalId, String family, String given, LocalDate birthDate, String sex)
            throws ca.uhn.hl7v2.HL7Exception {
        terser.set(prefix + "-3-1", externalId);
        terser.set(prefix + "-3-4", organizationId);
        terser.set(prefix + "-5-1", family);
        terser.set(prefix + "-5-2", given);
        terser.set(prefix + "-7", birthDate.format(HL7_DATE));
        terser.set(prefix + "-8", hl7Sex(sex));
    }

    public static String hl7Sex(String administrativeSex) {
        return switch (administrativeSex) {
            case "female" -> "F";
            case "male" -> "M";
            case "unknown" -> "U";
            default -> "";
        };
    }

    public static String administrativeSex(String hl7Sex) {
        return switch (hl7Sex == null ? "" : hl7Sex.trim().toUpperCase(Locale.ROOT)) {
            case "F" -> "female";
            case "M" -> "male";
            case "U" -> "unknown";
            default -> "";
        };
    }

    public static String orderStatus(String status) {
        return switch (status) {
            case "ORDERED" -> "SC";
            case "IN_PROGRESS" -> "IP";
            case "COMPLETED" -> "CM";
            case "CANCELLED" -> "CA";
            default -> "";
        };
    }

    public static String domainOrderStatus(String hl7Status) {
        return switch (hl7Status == null ? "" : hl7Status.trim().toUpperCase(Locale.ROOT)) {
            case "SC" -> "ORDERED";
            case "IP" -> "IN_PROGRESS";
            case "CM" -> "COMPLETED";
            case "CA" -> "CANCELLED";
            default -> "";
        };
    }

    public static String resultFlag(String status) {
        return switch (status) {
            case "PRELIMINARY" -> "P";
            case "FINAL" -> "F";
            case "CANCELLED" -> "X";
            default -> "";
        };
    }

    public static String domainResultStatus(String flag) {
        return switch (flag == null ? "" : flag.trim().toUpperCase(Locale.ROOT)) {
            case "P" -> "PRELIMINARY";
            case "F" -> "FINAL";
            case "X" -> "CANCELLED";
            default -> "";
        };
    }

    public static String hl7Time(OffsetDateTime value) {
        return HL7_TIME.format(value.withOffsetSameInstant(ZoneOffset.UTC));
    }

    public static OffsetDateTime parseTime(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        String text = value.trim();
        if (text.length() == 14) {
            text = text + "+0000";
        }
        return OffsetDateTime.parse(text, HL7_TIME);
    }

    public static LocalDate parseDate(String value) {
        if (value == null || value.length() < 8) {
            return null;
        }
        return LocalDate.parse(value.substring(0, 8), HL7_DATE);
    }

    public static boolean forbiddenCodeSystem(String system) {
        if (system == null) {
            return false;
        }
        String lower = system.toLowerCase(Locale.ROOT);
        return lower.contains("loinc") || lower.contains("ucum");
    }

    private static boolean numeric(String value) {
        return value != null && value.matches("-?(?:0|[1-9]\\d*)(?:\\.\\d+)?");
    }

    private Message newAck(String trigger) throws Exception {
        ca.uhn.hl7v2.model.v251.message.ACK ack = new ca.uhn.hl7v2.model.v251.message.ACK();
        ack.initQuickstart("ACK", trigger, "P");
        return ack;
    }

    private Message newOru() throws Exception {
        ca.uhn.hl7v2.model.v251.message.ORU_R01 oru = new ca.uhn.hl7v2.model.v251.message.ORU_R01();
        oru.initQuickstart("ORU", "R01", "P");
        return oru;
    }

    public static String value(Terser terser, String path) {
        try {
            String value = terser.get(path);
            return value == null ? "" : value.trim();
        } catch (Exception ex) {
            return "";
        }
    }

    public record ParsedMessage(String type, String event, Terser terser, Message message) {
    }

    public record OmlPayload(
            String sendingApplication,
            String sendingFacility,
            String receivingApplication,
            String receivingFacility,
            String security,
            String messageControlId,
            String organizationId,
            String externalPatientId,
            String familyName,
            String givenName,
            LocalDate birthDate,
            String administrativeSex,
            String placerOrderId,
            String testCode,
            String testDescription,
            String testSystem,
            OffsetDateTime requestedAt) {
    }

    public record OruPayload(
            String sendingApplication,
            String sendingFacility,
            String receivingApplication,
            String receivingFacility,
            String security,
            String messageControlId,
            String organizationId,
            String externalPatientId,
            String familyName,
            String givenName,
            LocalDate birthDate,
            String administrativeSex,
            String placerOrderId,
            String fillerOrderId,
            String orderStatus,
            String testCode,
            String testDescription,
            OffsetDateTime requestedAt,
            String externalResultId,
            String value,
            String unit,
            String referenceRange,
            String resultStatus,
            OffsetDateTime resultedAt) {
    }
}
