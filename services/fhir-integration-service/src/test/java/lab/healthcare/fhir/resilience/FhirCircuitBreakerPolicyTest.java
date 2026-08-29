package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.exception.FhirErrorCategory;

import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FhirCircuitBreakerPolicyTest {

    private final FhirCircuitBreakerPolicy policy = FhirCircuitBreakerPolicy.defaults();

    @Test
    void defaultsMatchLearningFoundation() {
        assertThat(policy.failureThreshold()).isEqualTo(3);
        assertThat(policy.resetTimeout()).isEqualTo(Duration.ofSeconds(30));
    }

    @Test
    void onlyInfrastructureCategoriesAffectTheCircuit() {
        assertThat(policy.affectsCircuit(FhirErrorCategory.SERVER_ERROR)).isTrue();
        assertThat(policy.affectsCircuit(FhirErrorCategory.TIMEOUT)).isTrue();
        assertThat(policy.affectsCircuit(FhirErrorCategory.CONNECTION_ERROR)).isTrue();
        assertThat(policy.affectsCircuit(FhirErrorCategory.NOT_FOUND)).isFalse();
        assertThat(policy.affectsCircuit(FhirErrorCategory.VALIDATION_ERROR)).isFalse();
        assertThat(policy.affectsCircuit(FhirErrorCategory.AUTHENTICATION_ERROR)).isFalse();
        assertThat(policy.affectsCircuit(FhirErrorCategory.AUTHORIZATION_ERROR)).isFalse();
        assertThat(policy.affectsCircuit(FhirErrorCategory.CONFLICT)).isFalse();
        assertThat(policy.affectsCircuit(FhirErrorCategory.UNKNOWN)).isFalse();
        assertThat(policy.affectsCircuit(FhirErrorCategory.CIRCUIT_OPEN)).isFalse();
    }

    @Test
    void rejectsInvalidBounds() {
        assertThatThrownBy(() -> new FhirCircuitBreakerPolicy(0, Duration.ofSeconds(30)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("failureThreshold");
        assertThatThrownBy(() -> new FhirCircuitBreakerPolicy(3, Duration.ZERO))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("resetTimeout");
    }
}
