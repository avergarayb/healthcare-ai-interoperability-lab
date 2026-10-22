package lab.healthcare.minilis;

/**
 * Explicit order transitions shared by the REST API and a future HL7 v2 adapter.
 * A final result is allowed while the order is still open so one order can hold
 * several results. Completion is a separate step and requires one final result.
 */
final class OrderTransition {

    private OrderTransition() {
    }

    static OrderStatus afterResult(OrderStatus current) {
        if (current == OrderStatus.ORDERED) {
            return OrderStatus.IN_PROGRESS;
        }
        if (current == OrderStatus.IN_PROGRESS) {
            return OrderStatus.IN_PROGRESS;
        }
        throw MiniLisException.invalidTransition();
    }

    static void requireCompletable(OrderStatus current, boolean hasFinalResult) {
        if (current != OrderStatus.IN_PROGRESS || !hasFinalResult) {
            throw MiniLisException.invalidTransition();
        }
    }

    static void requireCancellable(OrderStatus current, boolean hasFinalResult) {
        if ((current != OrderStatus.ORDERED && current != OrderStatus.IN_PROGRESS) || hasFinalResult) {
            throw MiniLisException.invalidTransition();
        }
    }
}
