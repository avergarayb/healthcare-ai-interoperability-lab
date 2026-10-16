package lab.healthcare.minihis;

import java.util.List;

public record ResultView(
        String resultId,
        String consultationId,
        String patientId,
        String resultType,
        String displayName,
        String valueText,
        String unit,
        String observedAt,
        String status,
        List<ResultComponentView> components) {
}
