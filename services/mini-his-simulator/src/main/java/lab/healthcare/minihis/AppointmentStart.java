package lab.healthcare.minihis;

import java.time.Clock;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;

/**
 * Synthetic starts are a signed number of days from the UTC date of the clock,
 * at 12:00Z. The stored offset is not rewritten on startup, so a negative
 * offset remains in the past and a positive offset remains in the future.
 */
public final class AppointmentStart {

    public static final int PAST_OFFSET_DAYS = -400;
    public static final int FUTURE_OFFSET_DAYS = 400;

    private AppointmentStart() {
    }

    public static String atOffset(int offsetDays, Clock clock) {
        LocalDate day = LocalDate.now(clock).plusDays(offsetDays);
        return OffsetDateTime.of(day.atTime(12, 0), ZoneOffset.UTC).toString();
    }
}
