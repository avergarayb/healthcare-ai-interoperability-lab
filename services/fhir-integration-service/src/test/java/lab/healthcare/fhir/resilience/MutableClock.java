package lab.healthcare.fhir.resilience;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;

/**
 * Test clock. Production uses {@link Clock#systemUTC()}.
 */
public final class MutableClock extends Clock {

    private Instant instant;
    private final ZoneId zone = ZoneOffset.UTC;

    public MutableClock(Instant instant) {
        this.instant = instant;
    }

    public static MutableClock epoch() {
        return new MutableClock(Instant.EPOCH);
    }

    public void advance(Duration duration) {
        instant = instant.plus(duration);
    }

    @Override
    public ZoneId getZone() {
        return zone;
    }

    @Override
    public Clock withZone(ZoneId zone) {
        return Clock.fixed(instant, zone);
    }

    @Override
    public Instant instant() {
        return instant;
    }
}
