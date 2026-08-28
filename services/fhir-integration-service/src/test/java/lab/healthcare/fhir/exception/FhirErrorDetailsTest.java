package lab.healthcare.fhir.exception;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FhirErrorDetailsTest {

    @Test
    void summaryOmitsCredentialsAndPayloads() {
        FhirErrorDetails details = new FhirErrorDetails(
                FhirErrorCategory.NOT_FOUND,
                404,
                "READ",
                "local-hapi",
                "Patient",
                "does-not-exist",
                "FHIR resource not found");

        String line = details.toLogLine();
        assertThat(line).contains("category=NOT_FOUND");
        assertThat(line).contains("status=404");
        assertThat(line).contains("destination=local-hapi");
        assertThat(line).contains("resourceId=does-not-exist");
        assertThat(line).doesNotContain("access_token");
        assertThat(line).doesNotContain("client_secret");
        assertThat(line).doesNotContain("refresh_token");
        assertThat(line).doesNotContain("Garcia");
        assertThat(line).doesNotContain("{");
    }

    @Test
    void rejectsCredentialMarkersInTheMessage() {
        assertThatThrownBy(() -> FhirErrorDetails.of(
                        FhirErrorCategory.AUTHENTICATION_ERROR, 401, "Bearer eyJhbGciOiJIUzI1NiJ9"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("credentials");
    }
}
