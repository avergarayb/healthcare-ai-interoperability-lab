package lab.healthcare.fhir.observability;

/**
 * Replaceable metrics sink. Consumes the same completed {@link FhirAuditEvent}
 * as audit, then aggregates. Does not retain individual clinical payloads.
 */
public interface FhirMetricsRecorder {

    void record(FhirAuditEvent event);

    FhirMetricSnapshot snapshot();
}
