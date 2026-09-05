package lab.healthcare.fhir.projection;

import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import java.util.List;

/**
 * Collection-level retention diagnosis plus allowlisted records. The laboratory
 * page must not render {@link #items()}.
 */
public record ProjectedCollection<T>(
        ClinicalSnapshotResourceStatus status,
        Integer receivedCount,
        Integer retainedCount,
        Boolean truncated,
        List<T> items) {

    public ProjectedCollection {
        items = items == null ? List.of() : List.copyOf(items);
    }

    public static <T> ProjectedCollection<T> unavailable() {
        return new ProjectedCollection<>(ClinicalSnapshotResourceStatus.UNAVAILABLE, null, null, null, List.of());
    }

    public static <T> ProjectedCollection<T> failed(ClinicalSnapshotResourceStatus status) {
        return new ProjectedCollection<>(status, null, null, null, List.of());
    }

    public static <T> ProjectedCollection<T> retained(
            int receivedCount, int retainedCount, boolean truncated, List<T> items) {
        return new ProjectedCollection<>(
                ClinicalSnapshotResourceStatus.SUCCESS, receivedCount, retainedCount, truncated, items);
    }
}
