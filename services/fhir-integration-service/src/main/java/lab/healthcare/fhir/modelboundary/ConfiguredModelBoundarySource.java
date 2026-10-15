package lab.healthcare.fhir.modelboundary;

/**
 * Source for {@code GET /api/model-boundary/v1}. The active FHIR destination
 * chooses an existing projection. This type does not name a vendor.
 */
@FunctionalInterface
public interface ConfiguredModelBoundarySource {

    ModelBoundaryContract currentContract();
}
