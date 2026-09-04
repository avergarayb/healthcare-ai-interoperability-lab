package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.patient.PatientContextSource;

import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.server.exceptions.AuthenticationException;
import ca.uhn.fhir.rest.server.exceptions.ForbiddenOperationException;
import ca.uhn.fhir.rest.server.exceptions.InternalErrorException;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.Observation;
import org.junit.jupiter.api.Test;

import java.net.SocketTimeoutException;

import static org.assertj.core.api.Assertions.assertThat;

class FhirObservationSearchResultsTest {

    @Test
    void succeededRecordsBundleMetadataWithoutPayload() {
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);
        Observation observation = new Observation();
        observation.setId("secret-observation");
        bundle.addEntry().setResource(observation);

        FhirObservationSearchResult result = FhirObservationSearchResults.succeeded("oracle-health-sandbox", bundle);

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.OBSERVATION_SEARCH_SUCCEEDED);
        assertThat(result.resourceType()).isEqualTo("Observation");
        assertThat(result.responseType()).isEqualTo("Bundle");
        assertThat(result.httpStatus()).isEqualTo(200);
        assertThat(result.hasEntries()).isTrue();
        assertThat(result.contextSource()).isEqualTo(PatientContextSource.CONFIGURED);
        assertThat(result.toString()).doesNotContain("secret-observation");
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Observation/");
    }

    @Test
    void emptySearchsetIsStillASucceededSearch() {
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);

        FhirObservationSearchResult result = FhirObservationSearchResults.succeeded("oracle-health-sandbox", bundle);

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.OBSERVATION_SEARCH_SUCCEEDED);
        assertThat(result.hasEntries()).isFalse();
        assertThat(result.responseType()).isEqualTo("Bundle");
    }

    @Test
    void maps401ToAuthenticationRejected() {
        FhirObservationSearchResult result = FhirObservationSearchResults.fromFailure(
                "oracle-health-sandbox", FhirClientException.from(new AuthenticationException()));

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.AUTHENTICATION_REJECTED);
        assertThat(result.httpStatus()).isEqualTo(401);
        assertThat(result.dependencyCategory()).isEqualTo(FhirErrorCategory.AUTHENTICATION_ERROR);
        assertThat(result.toString()).doesNotContain("Bearer ");
    }

    @Test
    void maps403ToAuthorizationDenied() {
        FhirObservationSearchResult result = FhirObservationSearchResults.fromFailure(
                "oracle-health-sandbox", FhirClientException.from(new ForbiddenOperationException("forbidden")));

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.AUTHORIZATION_DENIED);
        assertThat(result.httpStatus()).isEqualTo(403);
        assertThat(result.dependencyCategory()).isEqualTo(FhirErrorCategory.AUTHORIZATION_ERROR);
    }

    @Test
    void mapsTimeoutAndConnectionToDependencyFailure() {
        FhirObservationSearchResult timeout = FhirObservationSearchResults.fromFailure(
                "oracle-health-sandbox",
                FhirClientException.from(new FhirClientConnectionException(
                        "timed out", new SocketTimeoutException("Read timed out"))));
        FhirObservationSearchResult connection = FhirObservationSearchResults.fromFailure(
                "oracle-health-sandbox",
                FhirClientException.from(new FhirClientConnectionException("connection refused")));
        FhirObservationSearchResult server = FhirObservationSearchResults.fromFailure(
                "oracle-health-sandbox", FhirClientException.from(new InternalErrorException("boom")));

        assertThat(timeout.outcome()).isEqualTo(FhirObservationSearchOutcome.DEPENDENCY_FAILURE);
        assertThat(timeout.dependencyCategory()).isEqualTo(FhirErrorCategory.TIMEOUT);
        assertThat(connection.dependencyCategory()).isEqualTo(FhirErrorCategory.CONNECTION_ERROR);
        assertThat(server.dependencyCategory()).isEqualTo(FhirErrorCategory.SERVER_ERROR);
        assertThat(timeout.toString()).doesNotContain("Read timed out");
    }

    @Test
    void contextNotConfiguredDoesNotClaimAClinicalRequest() {
        FhirObservationSearchResult result = FhirObservationSearchResult.contextNotConfigured("oracle-health-sandbox");

        assertThat(result.outcome()).isEqualTo(FhirObservationSearchOutcome.PATIENT_CONTEXT_NOT_CONFIGURED);
        assertThat(result.hasPatientContext()).isFalse();
        assertThat(result.httpStatus()).isNull();
    }
}
