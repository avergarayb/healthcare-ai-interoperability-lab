package lab.healthcare.minilis;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class OrderTransitionTest {

    @Test
    void firstResultOpensTheOrderAndFurtherResultsStayOpen() {
        assertThat(OrderTransition.afterResult(OrderStatus.ORDERED)).isEqualTo(OrderStatus.IN_PROGRESS);
        assertThat(OrderTransition.afterResult(OrderStatus.IN_PROGRESS)).isEqualTo(OrderStatus.IN_PROGRESS);
    }

    @Test
    void closedOrdersRejectAnotherResult() {
        assertThatThrownBy(() -> OrderTransition.afterResult(OrderStatus.COMPLETED))
                .isInstanceOf(MiniLisException.class)
                .hasMessage("invalid_transition");
        assertThatThrownBy(() -> OrderTransition.afterResult(OrderStatus.CANCELLED))
                .isInstanceOf(MiniLisException.class)
                .hasMessage("invalid_transition");
    }

    @Test
    void completionRequiresAnOpenOrderAndAFinalResult() {
        OrderTransition.requireCompletable(OrderStatus.IN_PROGRESS, true);
        assertThatThrownBy(() -> OrderTransition.requireCompletable(OrderStatus.ORDERED, true))
                .isInstanceOf(MiniLisException.class);
        assertThatThrownBy(() -> OrderTransition.requireCompletable(OrderStatus.IN_PROGRESS, false))
                .isInstanceOf(MiniLisException.class);
    }

    @Test
    void aFinalResultBlocksCancellation() {
        OrderTransition.requireCancellable(OrderStatus.ORDERED, false);
        OrderTransition.requireCancellable(OrderStatus.IN_PROGRESS, false);
        assertThatThrownBy(() -> OrderTransition.requireCancellable(OrderStatus.IN_PROGRESS, true))
                .isInstanceOf(MiniLisException.class);
        assertThatThrownBy(() -> OrderTransition.requireCancellable(OrderStatus.COMPLETED, false))
                .isInstanceOf(MiniLisException.class);
    }
}
