package lab.healthcare.fhir.observability;

import java.util.Map;
import java.util.StringJoiner;
import java.util.TreeMap;

/**
 * Point-in-time aggregation. Dimensions are bounded operational labels only:
 * operation, destination, resourceType, outcome. No correlation IDs, patient
 * identifiers, or credentials.
 */
public record FhirMetricSnapshot(
        long totalOperations,
        long successfulOperations,
        long failedOperations,
        Map<String, Long> operationsByType,
        Map<String, Long> operationsByDestination,
        Map<String, Long> operationsByResourceType,
        Map<String, Long> operationsByOutcome,
        long totalDurationMs,
        long operationCount,
        long retryAttempts,
        long operationsRetried) {

    public FhirMetricSnapshot {
        if (totalOperations < 0
                || successfulOperations < 0
                || failedOperations < 0
                || totalDurationMs < 0
                || operationCount < 0
                || retryAttempts < 0
                || operationsRetried < 0) {
            throw new IllegalArgumentException("Metric counters must be zero or positive");
        }
        operationsByType = copy(operationsByType);
        operationsByDestination = copy(operationsByDestination);
        operationsByResourceType = copy(operationsByResourceType);
        operationsByOutcome = copy(operationsByOutcome);
    }

    public long averageDurationMs() {
        if (operationCount == 0L) {
            return 0L;
        }
        return totalDurationMs / operationCount;
    }

    public String toSummaryLine() {
        StringJoiner line = new StringJoiner(" ");
        line.add("FHIR_METRICS");
        line.add("total=" + totalOperations);
        line.add("success=" + successfulOperations);
        line.add("failed=" + failedOperations);
        line.add("durationMs=" + totalDurationMs);
        line.add("avgDurationMs=" + averageDurationMs());
        line.add("retryAttempts=" + retryAttempts);
        line.add("operationsRetried=" + operationsRetried);
        addGroup(line, "operations", operationsByType);
        addGroup(line, "destinations", operationsByDestination);
        addGroup(line, "resourceTypes", operationsByResourceType);
        addGroup(line, "outcomes", operationsByOutcome);
        return FhirAuditEvent.requireSafe(line.toString());
    }

    private static Map<String, Long> copy(Map<String, Long> values) {
        if (values == null) {
            throw new IllegalArgumentException("Metric dimension map must be provided");
        }
        return Map.copyOf(new TreeMap<>(values));
    }

    private static void addGroup(StringJoiner line, String name, Map<String, Long> values) {
        if (values.isEmpty()) {
            return;
        }
        StringJoiner group = new StringJoiner(",");
        values.forEach((key, count) -> group.add(key + "=" + count));
        line.add(name + "[" + group + "]");
    }
}
