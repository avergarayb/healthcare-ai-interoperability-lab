package lab.healthcare.minihis;

public record EventView(
        String eventId,
        String patientId,
        String recordKind,
        String resourceId,
        String changeType,
        String occurredAt,
        String detail) {
}
