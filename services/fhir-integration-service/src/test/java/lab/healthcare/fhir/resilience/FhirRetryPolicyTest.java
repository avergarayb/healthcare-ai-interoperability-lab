package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.exception.FhirErrorCategory;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FhirRetryPolicyTest {

    private final FhirRetryPolicy policy = FhirRetryPolicy.defaults();

    @Test
    void permanentCategoriesAreNotRetryable() {
        assertThat(policy.isRetryable(FhirErrorCategory.VALIDATION_ERROR)).isFalse();
        assertThat(policy.isRetryable(FhirErrorCategory.AUTHENTICATION_ERROR)).isFalse();
        assertThat(policy.isRetryable(FhirErrorCategory.AUTHORIZATION_ERROR)).isFalse();
        assertThat(policy.isRetryable(FhirErrorCategory.NOT_FOUND)).isFalse();
        assertThat(policy.isRetryable(FhirErrorCategory.CONFLICT)).isFalse();
        assertThat(policy.isRetryable(FhirErrorCategory.UNKNOWN)).isFalse();
    }

    @Test
    void transientCategoriesAreRetryable() {
        assertThat(policy.isRetryable(FhirErrorCategory.SERVER_ERROR)).isTrue();
        assertThat(policy.isRetryable(FhirErrorCategory.TIMEOUT)).isTrue();
        assertThat(policy.isRetryable(FhirErrorCategory.CONNECTION_ERROR)).isTrue();
    }

    @Test
    void maxAttemptsMeansThreeTotalExecutions() {
        assertThat(policy.maxAttempts()).isEqualTo(3);
        assertThat(policy.decide(FhirErrorCategory.TIMEOUT, 1).retry()).isTrue();
        assertThat(policy.decide(FhirErrorCategory.TIMEOUT, 2).retry()).isTrue();
        assertThat(policy.decide(FhirErrorCategory.TIMEOUT, 3).retry()).isFalse();
        assertThat(policy.decide(FhirErrorCategory.NOT_FOUND, 1).retry()).isFalse();
    }

    @Test
    void exponentialBackoffIsDeterministic() {
        assertThat(policy.delayBeforeAttempt(1)).isZero();
        assertThat(policy.delayBeforeAttempt(2)).isEqualTo(100L);
        assertThat(policy.delayBeforeAttempt(3)).isEqualTo(200L);
        assertThat(policy.decide(FhirErrorCategory.CONNECTION_ERROR, 1).delayMs()).isEqualTo(100L);
        assertThat(policy.decide(FhirErrorCategory.CONNECTION_ERROR, 2).delayMs()).isEqualTo(200L);
        assertThat(policy.decide(FhirErrorCategory.CONNECTION_ERROR, 3).delayMs()).isZero();
    }

    @Test
    void rejectsInvalidBounds() {
        assertThatThrownBy(() -> new FhirRetryPolicy(0, 100))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("maxAttempts");
    }
}
