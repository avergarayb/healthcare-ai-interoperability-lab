package lab.healthcare.fhir.exception;

import ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FhirClientExceptionTest {

    @Test
    void preservesCauseAndSafeDetails() {
        ResourceNotFoundException cause = new ResourceNotFoundException("Patient/missing");
        FhirClientException exception = FhirClientException.from(cause);

        assertThat(exception.category()).isEqualTo(FhirErrorCategory.NOT_FOUND);
        assertThat(exception.details().status()).isEqualTo(404);
        assertThat(exception.getCause()).isSameAs(cause);
        assertThat(exception.getMessage()).isEqualTo("FHIR resource not found");
        assertThat(exception.getMessage()).doesNotContain("Patient/missing");
        assertThat(exception.details().toLogLine()).doesNotContain("access_token");
        assertThat(exception.details().toLogLine()).doesNotContain("Bearer ");
        assertThat(exception.details().toLogLine()).doesNotContain("resourceType\":\"Patient");
    }

    @Test
    void doesNotReclassifyAnAlreadyWrappedException() {
        FhirClientException original = FhirClientException.from(new ResourceNotFoundException("Patient/missing"));

        assertThat(FhirClientException.from(original)).isSameAs(original);
    }

    @Test
    void rejectsMissingDetails() {
        assertThatThrownBy(() -> new FhirClientException(null, new IllegalStateException("x")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Error details");
    }
}
