package lab.healthcare.fhir.modelboundary;

import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

/**
 * Patient section of the v1 model boundary. Never includes id, name, or birthDate.
 */
public record BoundaryPatient(ClinicalSnapshotResourceStatus status, String resourceType) {

    public BoundaryPatient {
        resourceType = resourceType == null ? "" : resourceType.trim();
    }
}
