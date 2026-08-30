package lab.healthcare.fhir.resilience.ratelimit;

import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.resilience.MutableClock;

import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FhirRateLimiterTest {

    private final MutableClock clock = MutableClock.epoch();
    private final FhirRateLimiter limiter = new FhirRateLimiter(
            "local-hapi", FhirRateLimiterPolicy.defaults(), clock);

    @Test
    void tenOperationsAreAllowedInTheWindow() {
        for (int i = 0; i < 10; i++) {
            limiter.acquire();
        }

        assertThat(limiter.acceptedInWindow()).isEqualTo(10);
    }

    @Test
    void eleventhOperationIsRejected() {
        for (int i = 0; i < 10; i++) {
            limiter.acquire();
        }

        assertThatThrownBy(limiter::acquire)
                .isInstanceOf(RateLimitExceededException.class)
                .hasMessage(FhirErrorCategory.RATE_LIMITED.safeMessage())
                .extracting(ex -> ((RateLimitExceededException) ex).details().destination())
                .isEqualTo("local-hapi");
        assertThat(limiter.acceptedInWindow()).isEqualTo(10);
    }

    @Test
    void newWindowResetsTheCounter() {
        for (int i = 0; i < 10; i++) {
            limiter.acquire();
        }
        clock.advance(Duration.ofSeconds(1));

        limiter.acquire();

        assertThat(limiter.acceptedInWindow()).isEqualTo(1);
    }

    @Test
    void concurrentAcquiresDoNotExceedTheLimit() throws InterruptedException {
        ExecutorService pool = Executors.newFixedThreadPool(20);
        CountDownLatch start = new CountDownLatch(1);
        AtomicInteger accepted = new AtomicInteger();
        AtomicInteger rejected = new AtomicInteger();
        try {
            for (int i = 0; i < 20; i++) {
                pool.execute(() -> {
                    await(start);
                    try {
                        limiter.acquire();
                        accepted.incrementAndGet();
                    } catch (RateLimitExceededException ex) {
                        rejected.incrementAndGet();
                    }
                });
            }
            start.countDown();
            pool.shutdown();
            assertThat(pool.awaitTermination(5, TimeUnit.SECONDS)).isTrue();
        } finally {
            pool.shutdownNow();
        }

        assertThat(accepted.get()).isEqualTo(10);
        assertThat(rejected.get()).isEqualTo(10);
        assertThat(limiter.acceptedInWindow()).isEqualTo(10);
    }

    @Test
    void rejectsInvalidPolicy() {
        assertThatThrownBy(() -> new FhirRateLimiterPolicy(0, Duration.ofSeconds(1)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("maxOperations");
    }

    private static void await(CountDownLatch latch) {
        try {
            latch.await();
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(ex);
        }
    }
}
