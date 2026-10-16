package lab.healthcare.minihis;

public record ResultView(
        String resultId,
        String consultationId,
        String patientId,
        String resultType,
        String displayName,
        String valueText,
        String unit,
        String observedAt,
        String status) {
}
