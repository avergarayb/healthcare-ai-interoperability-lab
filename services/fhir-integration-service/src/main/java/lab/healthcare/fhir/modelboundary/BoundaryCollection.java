package lab.healthcare.fhir.modelboundary;

import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import java.util.List;

/**
 * Collection metadata plus allowlisted records. The laboratory page must not
 * render {@link #records()}.
 */
public record BoundaryCollection<T>(
        ClinicalSnapshotResourceStatus status,
        Integer receivedCount,
        Integer retainedCount,
        Boolean truncated,
        List<T> records) {

    public BoundaryCollection {
        records = records == null ? List.of() : List.copyOf(records);
    }
}
