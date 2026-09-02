package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;

import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.server.exceptions.AuthenticationException;
import ca.uhn.fhir.rest.server.exceptions.ForbiddenOperationException;
import ca.uhn.fhir.rest.server.exceptions.InternalErrorException;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.Test;

import java.net.SocketTimeoutException;

import static org.assertj.core.api.Assertions.assertThat;

class FhirAuthenticatedReadResultsTest {

    @Test
    void succeededRecordsBundleMetadataWithoutPayload() {
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);
        bundle.addEntry().setResource(new Patient().setId("secret-patient"));

        FhirAuthenticatedReadResult result = FhirAuthenticatedReadResults.succeeded("oracle-health-sandbox", bundle);

        assertThat(result.outcome()).isEqualTo(FhirAuthenticatedReadOutcome.AUTHENTICATED_READ_SUCCEEDED);
        assertThat(result.resourceType()).isEqualTo("Patient");
        assertThat(result.responseType()).isEqualTo("Bundle");
        assertThat(result.httpStatus()).isEqualTo(200);
        assertThat(result.hasEntries()).isTrue();
        assertThat(result.toString()).doesNotContain("secret-patient");
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Patient/");
    }

    @Test
    void maps401ToAuthenticationRejected() {
        FhirAuthenticatedReadResult result = FhirAuthenticatedReadResults.fromFailure(
                "oracle-health-sandbox", FhirClientException.from(new AuthenticationException()));

        assertThat(result.outcome()).isEqualTo(FhirAuthenticatedReadOutcome.AUTHENTICATION_REJECTED);
        assertThat(result.httpStatus()).isEqualTo(401);
        assertThat(result.dependencyCategory()).isEqualTo(FhirErrorCategory.AUTHENTICATION_ERROR);
        assertThat(result.toString()).doesNotContain("Bearer ");
    }

    @Test
    void maps403ToAuthorizationDenied() {
        FhirAuthenticatedReadResult result = FhirAuthenticatedReadResults.fromFailure(
                "oracle-health-sandbox", FhirClientException.from(new ForbiddenOperationException("forbidden")));

        assertThat(result.outcome()).isEqualTo(FhirAuthenticatedReadOutcome.AUTHORIZATION_DENIED);
        assertThat(result.httpStatus()).isEqualTo(403);
        assertThat(result.dependencyCategory()).isEqualTo(FhirErrorCategory.AUTHORIZATION_ERROR);
    }

    @Test
    void mapsTimeoutAndConnectionToDependencyFailure() {
        FhirAuthenticatedReadResult timeout = FhirAuthenticatedReadResults.fromFailure(
                "oracle-health-sandbox",
                FhirClientException.from(new FhirClientConnectionException(
                        "timed out", new SocketTimeoutException("Read timed out"))));
        FhirAuthenticatedReadResult connection = FhirAuthenticatedReadResults.fromFailure(
                "oracle-health-sandbox",
                FhirClientException.from(new FhirClientConnectionException("connection refused")));
        FhirAuthenticatedReadResult server = FhirAuthenticatedReadResults.fromFailure(
                "oracle-health-sandbox", FhirClientException.from(new InternalErrorException("boom")));

        assertThat(timeout.outcome()).isEqualTo(FhirAuthenticatedReadOutcome.DEPENDENCY_FAILURE);
        assertThat(timeout.dependencyCategory()).isEqualTo(FhirErrorCategory.TIMEOUT);
        assertThat(connection.dependencyCategory()).isEqualTo(FhirErrorCategory.CONNECTION_ERROR);
        assertThat(server.dependencyCategory()).isEqualTo(FhirErrorCategory.SERVER_ERROR);
        assertThat(timeout.toString()).doesNotContain("Read timed out");
    }
}
