package lab.healthcare.minihis;

import java.util.List;

public record ResultSearch(List<ResultView> results, boolean truncated) {
}
