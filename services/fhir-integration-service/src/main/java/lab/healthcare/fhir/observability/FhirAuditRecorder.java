package lab.healthcare.fhir.observability;

public interface FhirAuditRecorder {

    void record(FhirAuditEvent event);
}
