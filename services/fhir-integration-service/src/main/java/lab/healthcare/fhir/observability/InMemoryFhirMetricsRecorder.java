package lab.healthcare.fhir.observability;

import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Lab aggregator: in-memory counters for local development and tests.
 * Not a metrics database, Prometheus server, or OpenTelemetry collector.
 */
@Component
public class InMemoryFhirMetricsRecorder implements FhirMetricsRecorder {

    private long totalOperations;
    private long successfulOperations;
    private long failedOperations;
    private long totalDurationMs;
    private long operationCount;
    private final Map<String, Long> operationsByType = new LinkedHashMap<>();
    private final Map<String, Long> operationsByDestination = new LinkedHashMap<>();
    private final Map<String, Long> operationsByResourceType = new LinkedHashMap<>();
    private final Map<String, Long> operationsByOutcome = new LinkedHashMap<>();

    @Override
    public synchronized void record(FhirAuditEvent event) {
        if (event == null) {
            throw new IllegalArgumentException("Audit event must be provided");
        }
        FhirOperationContext context = event.context();
        totalOperations++;
        operationCount++;
        totalDurationMs += event.durationMs();
        increment(operationsByType, context.operation().name());
        increment(operationsByDestination, context.destination());
        increment(operationsByResourceType, context.resourceType());
        increment(operationsByOutcome, event.outcome().name());
        if (event.outcome() == FhirAuditOutcome.SUCCESS) {
            successfulOperations++;
        } else {
            failedOperations++;
        }
    }

    @Override
    public synchronized FhirMetricSnapshot snapshot() {
        return new FhirMetricSnapshot(
                totalOperations,
                successfulOperations,
                failedOperations,
                Map.copyOf(operationsByType),
                Map.copyOf(operationsByDestination),
                Map.copyOf(operationsByResourceType),
                Map.copyOf(operationsByOutcome),
                totalDurationMs,
                operationCount);
    }

    private static void increment(Map<String, Long> counters, String dimension) {
        counters.merge(dimension, 1L, Long::sum);
    }
}
