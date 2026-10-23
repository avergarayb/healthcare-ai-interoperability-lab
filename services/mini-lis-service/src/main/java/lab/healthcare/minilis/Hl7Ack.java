package lab.healthcare.minilis;

/**
 * Stored ACK for one HL7 message control id. The detail is an identifier
 * correlation or an error code. It does not carry a clinical value.
 */
public record Hl7Ack(String code, String detail, String fillerOrderId, String patientId, boolean duplicate) {

    static Hl7Ack accepted(String fillerOrderId, String patientId, boolean duplicate) {
        String detail = "order=" + fillerOrderId + "&patient=" + patientId + "&duplicate=" + duplicate;
        return new Hl7Ack("AA", detail, fillerOrderId, patientId, duplicate);
    }

    static Hl7Ack error(String code, String detail) {
        return new Hl7Ack(code, detail, null, null, false);
    }

    static Hl7Ack fromStored(String code, String detail) {
        String order = token(detail, "order");
        String patient = token(detail, "patient");
        boolean duplicate = "true".equals(token(detail, "duplicate"));
        return new Hl7Ack(code, detail, order, patient, duplicate);
    }

    private static String token(String detail, String name) {
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
}
