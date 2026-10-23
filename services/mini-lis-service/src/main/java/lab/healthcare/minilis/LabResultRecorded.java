package lab.healthcare.minilis;

/**
 * Published after a result commits. The payload is identifiers only.
 */
public record LabResultRecorded(String orderId, String resultId) {
}
