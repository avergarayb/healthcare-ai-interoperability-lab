package lab.healthcare.fhir.snapshot;

/**
 * Which collection searches a snapshot includes. Vendor adapters choose a
 * contents object; {@link ClinicalSnapshotAssembler} does not switch on vendor.
 */
public record ClinicalSnapshotContents(boolean includeMedicationRequests) {

    public static ClinicalSnapshotContents allCollections() {
        return new ClinicalSnapshotContents(true);
    }

    public static ClinicalSnapshotContents withoutMedicationRequests() {
        return new ClinicalSnapshotContents(false);
    }
}
