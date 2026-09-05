package lab.healthcare.fhir.modelboundary;

/**
 * Vendor-neutral source of the current v1 contract. Implementations wire a
 * destination; this type does not name Oracle or Epic.
 */
@FunctionalInterface
public interface ModelBoundaryContractProvider {

    ModelBoundaryContract currentContract();
}
