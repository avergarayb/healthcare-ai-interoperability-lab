package lab.healthcare.minilis;

/**
 * One stored inbound HL7 decision. The digest is of the received message.
 * An empty digest is a row written before the sender-scoped key existed.
 */
public record StoredHl7Message(Hl7Ack ack, String digest) {
}
