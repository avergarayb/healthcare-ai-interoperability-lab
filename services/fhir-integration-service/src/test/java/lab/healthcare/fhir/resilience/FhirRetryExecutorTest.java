package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorDetails;

import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException;
import org.junit.jupiter.api.Test;

import java.net.SocketTimeoutException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FhirRetryExecutorTest {

    private final List<Long> waits = new ArrayList<>();
    private final List<FhirRetryAttempt> attempts = new ArrayList<>();
    private final FhirRetryExecutor executor = FhirRetryExecutor.of(
            FhirRetryPolicy.defaults(), waits::add);

    @Test
    void succeedsOnFirstAttemptWithoutWaiting() {
        String result = executor.execute(() -> "ok", attempts::add);

        assertThat(result).isEqualTo("ok");
        assertThat(attempts).hasSize(1);
        assertThat(attempts.getFirst().attempt()).isEqualTo(1);
        assertThat(attempts.getFirst().success()).isTrue();
        assertThat(waits).isEmpty();
    }

    @Test
    void retriesTimeoutThenSucceeds() {
        AtomicInteger calls = new AtomicInteger();
        String result = executor.execute(() -> {
            if (calls.incrementAndGet() == 1) {
                throw timeout();
            }
            return "recovered";
        }, attempts::add);

        assertThat(result).isEqualTo("recovered");
        assertThat(calls.get()).isEqualTo(2);
        assertThat(attempts).hasSize(2);
        assertThat(attempts.getFirst().success()).isFalse();
        assertThat(attempts.getFirst().willRetry()).isTrue();
        assertThat(attempts.getLast().success()).isTrue();
        assertThat(waits).containsExactly(100L);
    }

    @Test
    void exhaustsConnectionErrorsAndPreservesStructuredException() {
        FhirClientException failure = connection();
        assertThatThrownBy(() -> executor.execute(() -> {
                    throw failure;
                }, attempts::add))
                .isSameAs(failure)
                .extracting(ex -> ((FhirClientException) ex).category())
                .isEqualTo(FhirErrorCategory.CONNECTION_ERROR);

        assertThat(attempts).hasSize(3);
        assertThat(attempts.get(0).willRetry()).isTrue();
        assertThat(attempts.get(1).willRetry()).isTrue();
        assertThat(attempts.get(2).willRetry()).isFalse();
        assertThat(waits).containsExactly(100L, 200L);
        assertThat(failure.getMessage()).doesNotContain("access_token");
    }

    @Test
    void notFoundFailsImmediately() {
        FhirClientException missing = FhirClientException.from(new ResourceNotFoundException("Patient/missing"));
        AtomicInteger calls = new AtomicInteger();

        assertThatThrownBy(() -> executor.execute(() -> {
                    calls.incrementAndGet();
                    throw missing;
                }, attempts::add))
                .isSameAs(missing)
                .extracting(ex -> ((FhirClientException) ex).category())
                .isEqualTo(FhirErrorCategory.NOT_FOUND);

        assertThat(calls.get()).isEqualTo(1);
        assertThat(attempts).hasSize(1);
        assertThat(attempts.getFirst().willRetry()).isFalse();
        assertThat(waits).isEmpty();
    }

    private static FhirClientException timeout() {
        return FhirClientException.from(
                new FhirClientConnectionException("timed out", new SocketTimeoutException("Read timed out")));
    }

    private static FhirClientException connection() {
        return new FhirClientException(
                FhirErrorDetails.of(FhirErrorCategory.CONNECTION_ERROR, null),
                new FhirClientConnectionException("connection refused"));
    }
}
