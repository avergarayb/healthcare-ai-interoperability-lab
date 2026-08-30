package lab.healthcare.fhir.resilience.bulkhead;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FhirBulkheadRegistryTest {

    @Test
    void isolatesCapacityPerDestination() {
        FhirBulkheadRegistry registry = FhirBulkheadRegistry.of(FhirBulkheadPolicy.defaults());
        FhirBulkhead destinationA = registry.forDestination("destination-a");
        FhirBulkhead destinationB = registry.forDestination("destination-b");

        for (int i = 0; i < 5; i++) {
            destinationA.acquire();
        }

        assertThatThrownBy(destinationA::acquire).isInstanceOf(BulkheadFullException.class);
        destinationB.acquire();
        assertThat(destinationB.availablePermits()).isEqualTo(4);
        assertThat(registry.forDestination("destination-a")).isSameAs(destinationA);
    }
}
