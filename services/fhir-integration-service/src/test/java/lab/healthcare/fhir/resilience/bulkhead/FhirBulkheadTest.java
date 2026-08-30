package lab.healthcare.fhir.resilience.bulkhead;

import lab.healthcare.fhir.exception.FhirErrorCategory;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FhirBulkheadTest {

    private final FhirBulkhead bulkhead = new FhirBulkhead("local-hapi", FhirBulkheadPolicy.defaults());

    @Test
    void availableCapacityAllowsEntry() {
        bulkhead.acquire();

        assertThat(bulkhead.availablePermits()).isEqualTo(4);
        bulkhead.release();
        assertThat(bulkhead.availablePermits()).isEqualTo(5);
    }

    @Test
    void exhaustedCapacityRejectsImmediately() {
        holdAllPermits();

        assertThatThrownBy(bulkhead::acquire)
                .isInstanceOf(BulkheadFullException.class)
                .hasMessage(FhirErrorCategory.BULKHEAD_FULL.safeMessage())
                .extracting(ex -> ((BulkheadFullException) ex).details().destination())
                .isEqualTo("local-hapi");
        assertThat(bulkhead.availablePermits()).isZero();
    }

    @Test
    void executeReleasesPermitOnSuccess() {
        String result = bulkhead.execute(() -> "ok");

        assertThat(result).isEqualTo("ok");
        assertThat(bulkhead.availablePermits()).isEqualTo(5);
    }

    @Test
    void executeReleasesPermitOnFailure() {
        assertThatThrownBy(() -> bulkhead.execute(() -> {
                    throw new IllegalStateException("fhir failed");
                }))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("fhir failed");

        assertThat(bulkhead.availablePermits()).isEqualTo(5);
    }

    @Test
    void rejectsInvalidPolicy() {
        assertThatThrownBy(() -> new FhirBulkheadPolicy(0))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("maxConcurrentOperations");
    }

    private void holdAllPermits() {
        for (int i = 0; i < 5; i++) {
            bulkhead.acquire();
        }
    }
}
