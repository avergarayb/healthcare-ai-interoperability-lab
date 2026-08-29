package lab.healthcare.fhir.resilience;

@FunctionalInterface
public interface FhirRetryObserver {

    void onAttempt(FhirRetryAttempt attempt);
}
