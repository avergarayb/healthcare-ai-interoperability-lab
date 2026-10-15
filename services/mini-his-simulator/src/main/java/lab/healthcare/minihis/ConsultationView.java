package lab.healthcare.minihis;

public record ConsultationView(
        String consultationId,
        String patientId,
        String occurredAt,
        String reason,
        String clinicianName,
        String status) {
}
