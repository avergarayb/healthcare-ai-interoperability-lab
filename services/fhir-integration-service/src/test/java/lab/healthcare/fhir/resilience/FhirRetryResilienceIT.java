package lab.healthcare.fhir.resilience;

import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;

import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.net.SocketTimeoutException;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class FhirRetryResilienceIT {

    @Autowired
    private FhirRetryExecutor retryExecutor;

    @Test
    void springRetryExecutorUsesBoundedDefaultPolicy() {
        assertThat(retryExecutor.policy().maxAttempts()).isEqualTo(3);
        assertThat(retryExecutor.policy().initialDelayMs()).isEqualTo(100L);
    }

    @Test
    void transientFailureThenSuccessWithoutSleepingInTests() {
        FhirRetryExecutor fast = FhirRetryExecutor.immediate();
        AtomicInteger calls = new AtomicInteger();

        String result = fast.execute(() -> {
            if (calls.incrementAndGet() == 1) {
                throw FhirClientException.from(
                        new FhirClientConnectionException("timed out", new SocketTimeoutException("Read timed out")));
            }
            return "ok";
        });

        assertThat(result).isEqualTo("ok");
        assertThat(calls.get()).isEqualTo(2);
        assertThat(FhirErrorCategory.TIMEOUT.safeMessage()).doesNotContain("access_token");
    }
}
