package lab.healthcare.fhir.projection;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class RetentionCeilingTest {

    private final RetentionCeiling ceiling = new RetentionCeiling();

    @Test
    void defaultLimitIsFive() {
        assertThat(ceiling.limit()).isEqualTo(5);
    }

    @Test
    void receivedZeroIsRetainedZeroAndNotTruncated() {
        assertThat(ceiling.retain(0)).isZero();
        assertThat(ceiling.truncated(0)).isFalse();
    }

    @Test
    void receivedOneIsRetainedOne() {
        assertThat(ceiling.retain(1)).isEqualTo(1);
        assertThat(ceiling.truncated(1)).isFalse();
    }

    @Test
    void receivedFiveIsRetainedFiveAndNotTruncated() {
        assertThat(ceiling.retain(5)).isEqualTo(5);
        assertThat(ceiling.truncated(5)).isFalse();
    }

    @Test
    void receivedSixIsRetainedFiveAndTruncated() {
        assertThat(ceiling.retain(6)).isEqualTo(5);
        assertThat(ceiling.truncated(6)).isTrue();
    }

    @Test
    void received1489IsRetainedFiveAndTruncated() {
        assertThat(ceiling.retain(1489)).isEqualTo(5);
        assertThat(ceiling.truncated(1489)).isTrue();
    }

    @Test
    void negativeReceivedIsRejected() {
        assertThatThrownBy(() -> ceiling.retain(-1)).isInstanceOf(IllegalArgumentException.class);
    }
}
