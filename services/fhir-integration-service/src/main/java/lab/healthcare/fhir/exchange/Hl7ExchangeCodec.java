package lab.healthcare.fhir.exchange;

import ca.uhn.hl7v2.DefaultHapiContext;
import ca.uhn.hl7v2.HapiContext;
import ca.uhn.hl7v2.model.Message;
import ca.uhn.hl7v2.parser.Parser;
import ca.uhn.hl7v2.util.Terser;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.Locale;

/**
 * Builds OML^O21 and reads ACK and ORU^R01 for the v2.5.1 laboratory profile.
 * Code systems that name LOINC or UCUM are rejected instead of translated.
 */
final class Hl7ExchangeCodec {

    static final String VERSION = "2.5.1";
    private static final DateTimeFormatter HL7_TIME = DateTimeFormatter.ofPattern("yyyyMMddHHmmssZ");
    private static final DateTimeFormatter HL7_DATE = DateTimeFormatter.ofPattern("yyyyMMdd");

    static {
        if (System.getProperty("hapi.home") == null) {
            System.setProperty("hapi.home", System.getProperty("java.io.tmpdir"));
        }
    }

    private final HapiContext context = new DefaultHapiContext();
    private final Parser parser;

    Hl7ExchangeCodec() {
        context.getParserConfiguration().setValidating(false);
        parser = context.getPipeParser();
    }

    synchronized String oml(ExchangeProperties.Hl7 peer, String controlId, String security, DestinationCommand command, PatientIdentity patient) {
        try {
            ca.uhn.hl7v2.model.v251.message.OML_O21 message = new ca.uhn.hl7v2.model.v251.message.OML_O21();
            message.initQuickstart("OML", "O21", "P");
            Terser terser = new Terser(message);
            terser.set("/MSH-3", peer.getSendingApplication());
            terser.set("/MSH-4", peer.getSendingFacility());
            terser.set("/MSH-5", peer.getReceivingApplication());
            terser.set("/MSH-6", peer.getReceivingFacility());
            terser.set("/MSH-8", security);
            terser.set("/MSH-10", controlId);
            terser.set("/MSH-11", "P");
            terser.set("/MSH-12", VERSION);
            terser.set("/MSH-18", "UNICODE UTF-8");
            terser.set("/PATIENT/PID-3-1", patient.identifierValue());
            terser.set("/PATIENT/PID-3-4", command.requestingOrganizationId());
            terser.set("/PATIENT/PID-5-1", patient.familyName());
            terser.set("/PATIENT/PID-5-2", patient.givenName());
            terser.set("/PATIENT/PID-7", patient.birthDate().format(HL7_DATE));
            terser.set("/PATIENT/PID-8", sex(patient.administrativeSex()));
            terser.set("/ORDER/ORC-1", "NW");
            terser.set("/ORDER/ORC-2-1", command.externalRequestId());
            terser.set("/ORDER/ORC-21-10", command.requestingOrganizationId());
            terser.set("/ORDER/OBSERVATION_REQUEST/OBR-1", "1");
            terser.set("/ORDER/OBSERVATION_REQUEST/OBR-2-1", command.externalRequestId());
            terser.set("/ORDER/OBSERVATION_REQUEST/OBR-4-1", command.testCode());
            terser.set("/ORDER/OBSERVATION_REQUEST/OBR-4-2", command.testDescription());
            terser.set("/ORDER/OBSERVATION_REQUEST/OBR-4-3", command.testSystem());
            terser.set("/ORDER/OBSERVATION_REQUEST/OBR-7", HL7_TIME.format(command.requestedAt().withOffsetSameInstant(ZoneOffset.UTC)));
            return parser.encode(message);
        } catch (Exception ex) {
            throw ExchangeException.invalidRequest();
        }
    }

    synchronized Ack ack(String er7) {
        Terser terser = terser(er7);
        if (terser == null) {
            return new Ack("AR", "", "invalid_request");
        }
        String code = value(terser, "/MSA-1");
        String controlId = value(terser, "/MSA-2");
        if ("ORL".equals(value(terser, "/MSH-9-1")) && "O22".equals(value(terser, "/MSH-9-2"))) {
            String orderId = value(terser, "/RESPONSE/PATIENT/ORDER/ORC-3-1");
            String patientId = value(terser, "/RESPONSE/PATIENT/PID-3-1");
            boolean duplicate = "duplicate".equals(value(terser, "/MSA-3"));
            return new Ack(code, controlId, "order=" + orderId + "&patient=" + patientId + "&duplicate=" + duplicate);
        }
        return new Ack(code, controlId, value(terser, "/MSA-3"));
    }

    synchronized Oru oru(String er7) {
        Terser terser = terser(er7);
        if (terser == null || !"ORU".equals(value(terser, "/MSH-9-1")) || !"R01".equals(value(terser, "/MSH-9-2"))) {
            return null;
        }
        String system = value(terser, "/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-3-3");
        String unitSystem = value(terser, "/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-6-3");
        if (forbidden(system) || forbidden(unitSystem) || forbidden(value(terser, "/PATIENT_RESULT/ORDER_OBSERVATION/OBR-4-3"))) {
            return new Oru(value(terser, "/MSH-10"), "", "", "", "", "", "", "", "", "", "", "", "", "", "", true);
        }
        return new Oru(
                value(terser, "/MSH-10"),
                value(terser, "/MSH-3"),
                value(terser, "/MSH-4"),
                value(terser, "/MSH-5"),
                value(terser, "/MSH-6"),
                value(terser, "/MSH-8"),
                value(terser, "/PATIENT_RESULT/PATIENT/PID-3-1"),
                value(terser, "/PATIENT_RESULT/PATIENT/PID-3-4"),
                value(terser, "/PATIENT_RESULT/ORDER_OBSERVATION/ORC-2-1"),
                value(terser, "/PATIENT_RESULT/ORDER_OBSERVATION/ORC-3-1"),
                value(terser, "/PATIENT_RESULT/ORDER_OBSERVATION/ORC-5"),
                value(terser, "/PATIENT_RESULT/ORDER_OBSERVATION/ORC-21-10"),
                value(terser, "/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-3-1"),
                value(terser, "/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-4"),
                value(terser, "/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-5"),
                value(terser, "/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-6-1"),
                value(terser, "/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-7"),
                value(terser, "/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-11"),
                value(terser, "/PATIENT_RESULT/ORDER_OBSERVATION/OBSERVATION/OBX-14"),
                false);
    }

    synchronized String ackMessage(ExchangeProperties.Hl7 peer, String trigger, String code, String controlId, String detail) {
        try {
            ca.uhn.hl7v2.model.v251.message.ACK ack = new ca.uhn.hl7v2.model.v251.message.ACK();
            ack.initQuickstart("ACK", trigger, "P");
            Terser terser = new Terser(ack);
            terser.set("/MSH-3", peer.getSendingApplication());
            terser.set("/MSH-4", peer.getSendingFacility());
            terser.set("/MSH-9-2", trigger);
            terser.set("/MSH-12", VERSION);
            terser.set("/MSA-1", code);
            terser.set("/MSA-2", controlId == null || controlId.isBlank() ? "UNKNOWN" : controlId);
            terser.set("/MSA-3", detail == null ? "" : detail);
            return parser.encode(ack);
        } catch (Exception ex) {
            return "MSH|^~\\&|FHIR-EXCHANGE|fhir-integration-service|||000000||ACK^R01|UNKNOWN|P|2.5.1\rMSA|AR|UNKNOWN|invalid_request\r";
        }
    }

    private Terser terser(String er7) {
        try {
            Message message = parser.parse(er7);
            return new Terser(message);
        } catch (Exception ex) {
            return null;
        }
    }

    static String value(Terser terser, String path) {
        try {
            String found = terser.get(path);
            return found == null ? "" : found.trim();
        } catch (Exception ex) {
            return "";
        }
    }

    static String token(String detail, String name) {
        if (detail == null) {
            return "";
        }
        for (String part : detail.split("&")) {
            int mark = part.indexOf('=');
            if (mark > 0 && name.equals(part.substring(0, mark))) {
                return part.substring(mark + 1);
            }
        }
        return "";
    }

    private static boolean forbidden(String system) {
        String lower = system == null ? "" : system.toLowerCase(Locale.ROOT);
        return lower.contains("loinc") || lower.contains("ucum");
    }

    private static String sex(String administrativeSex) {
        return switch (administrativeSex) {
            case "female" -> "F";
            case "male" -> "M";
            case "unknown" -> "U";
            default -> "U";
        };
    }

    static OffsetDateTime parseTime(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        String text = value.trim();
        if (text.length() == 14) {
            text = text + "+0000";
        }
        try {
            return OffsetDateTime.parse(text, HL7_TIME);
        } catch (RuntimeException ex) {
            return null;
        }
    }

    record Ack(String code, String controlId, String detail) {
    }

    record Oru(
            String controlId,
            String sendingApplication,
            String sendingFacility,
            String receivingApplication,
            String receivingFacility,
            String security,
            String externalPatientId,
            String organizationId,
            String placerOrderId,
            String fillerOrderId,
            String orderStatus,
            String orderingOrganizationId,
            String testCode,
            String externalResultId,
            String value,
            String unit,
            String referenceRange,
            String resultFlag,
            String resultedAt,
            boolean forbiddenCodeSystem) {

        Oru(
                String controlId,
                String sendingApplication,
                String sendingFacility,
                String receivingApplication,
                String receivingFacility,
                String security,
                String externalPatientId,
                String organizationId,
                String placerOrderId,
                String fillerOrderId,
                String orderStatus,
                String orderingOrganizationId,
                String testCode,
                String externalResultId,
                String value,
                boolean forbiddenCodeSystem) {
            this(controlId, sendingApplication, sendingFacility, receivingApplication, receivingFacility, security,
                    externalPatientId, organizationId, placerOrderId, fillerOrderId, orderStatus, orderingOrganizationId,
                    testCode, externalResultId, value, "", "", "", "", forbiddenCodeSystem);
        }
    }
}
