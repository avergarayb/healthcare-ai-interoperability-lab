package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.exception.FhirErrorCategory;

import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FhirCircuitBreakerTest {

    private final MutableClock clock = MutableClock.epoch();
    private final FhirCircuitBreaker breaker = new FhirCircuitBreaker(
            "local-hapi", FhirCircuitBreakerPolicy.defaults(), clock);

    @Test
    void successfulOperationLeavesCircuitClosed() {
        breaker.acquire();
        breaker.recordSuccess();

        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(breaker.consecutiveFailures()).isZero();
    }

    @Test
    void threeRetryableLogicalFailuresOpenTheCircuit() {
        failLogical(FhirErrorCategory.TIMEOUT);
        failLogical(FhirErrorCategory.CONNECTION_ERROR);
        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.CLOSED);
        failLogical(FhirErrorCategory.SERVER_ERROR);

        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.OPEN);
        assertThat(breaker.consecutiveFailures()).isEqualTo(3);
    }

    @Test
    void openFailsFastWithoutRunningTheSupplier() {
        openCircuit();
        AtomicInteger calls = new AtomicInteger();

        assertThatThrownBy(() -> {
                    breaker.acquire();
                    calls.incrementAndGet();
                })
                .isInstanceOf(CircuitBreakerOpenException.class)
                .hasMessage(FhirErrorCategory.CIRCUIT_OPEN.safeMessage())
                .extracting(ex -> ((CircuitBreakerOpenException) ex).details().destination())
                .isEqualTo("local-hapi");

        assertThat(calls.get()).isZero();
        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.OPEN);
    }

    @Test
    void resetTimeoutMovesOpenToHalfOpen() {
        openCircuit();
        clock.advance(Duration.ofSeconds(29));
        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.OPEN);

        clock.advance(Duration.ofSeconds(1));

        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.HALF_OPEN);
    }

    @Test
    void halfOpenSuccessClosesAndResetsFailures() {
        openCircuit();
        clock.advance(Duration.ofSeconds(30));
        breaker.acquire();
        breaker.recordSuccess();

        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(breaker.consecutiveFailures()).isZero();
    }

    @Test
    void halfOpenInfrastructureFailureReopens() {
        openCircuit();
        clock.advance(Duration.ofSeconds(30));
        breaker.acquire();
        breaker.recordFailure(FhirErrorCategory.TIMEOUT);

        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.OPEN);
    }

    @Test
    void halfOpenNotFoundClosesBecauseTheServerAnswered() {
        openCircuit();
        clock.advance(Duration.ofSeconds(30));
        breaker.acquire();
        breaker.recordFailure(FhirErrorCategory.NOT_FOUND);

        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(breaker.consecutiveFailures()).isZero();
    }

    @Test
    void nonRetryableFailuresDoNotOpenTheCircuit() {
        for (FhirErrorCategory category : new FhirErrorCategory[] {
                FhirErrorCategory.NOT_FOUND,
                FhirErrorCategory.VALIDATION_ERROR,
                FhirErrorCategory.AUTHENTICATION_ERROR,
                FhirErrorCategory.AUTHORIZATION_ERROR,
                FhirErrorCategory.CONFLICT
        }) {
            failLogical(category);
        }

        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(breaker.consecutiveFailures()).isZero();
    }

    @Test
    void retryThenSuccessDoesNotCountAsACircuitFailure() {
        breaker.acquire();
        breaker.recordSuccess();
        failLogical(FhirErrorCategory.TIMEOUT);
        failLogical(FhirErrorCategory.TIMEOUT);
        breaker.acquire();
        breaker.recordSuccess();

        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.CLOSED);
        assertThat(breaker.consecutiveFailures()).isZero();
    }

    @Test
    void halfOpenAllowsOnlyOneProbe() {
        openCircuit();
        clock.advance(Duration.ofSeconds(30));
        breaker.acquire();

        assertThatThrownBy(breaker::acquire)
                .isInstanceOf(CircuitBreakerOpenException.class);
        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.HALF_OPEN);
    }

    private void openCircuit() {
        failLogical(FhirErrorCategory.TIMEOUT);
        failLogical(FhirErrorCategory.TIMEOUT);
        failLogical(FhirErrorCategory.TIMEOUT);
        assertThat(breaker.state()).isEqualTo(CircuitBreakerState.OPEN);
    }

    private void failLogical(FhirErrorCategory category) {
        breaker.acquire();
        breaker.recordFailure(category);
    }
}
