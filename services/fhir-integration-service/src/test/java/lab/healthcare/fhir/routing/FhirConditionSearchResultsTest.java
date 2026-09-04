package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.patient.PatientContextSource;

import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.server.exceptions.AuthenticationException;
import ca.uhn.fhir.rest.server.exceptions.ForbiddenOperationException;
import ca.uhn.fhir.rest.server.exceptions.InternalErrorException;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.Condition;
import org.junit.jupiter.api.Test;

import java.net.SocketTimeoutException;

import static org.assertj.core.api.Assertions.assertThat;

class FhirConditionSearchResultsTest {

    @Test
    void succeededRecordsBundleMetadataWithoutPayload() {
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);
        Condition condition = new Condition();
        condition.setId("secret-condition");
        bundle.addEntry().setResource(condition);

        FhirConditionSearchResult result = FhirConditionSearchResults.succeeded("oracle-health-sandbox", bundle);

        assertThat(result.outcome()).isEqualTo(FhirConditionSearchOutcome.CONDITION_SEARCH_SUCCEEDED);
        assertThat(result.resourceType()).isEqualTo("Condition");
        assertThat(result.responseType()).isEqualTo("Bundle");
        assertThat(result.httpStatus()).isEqualTo(200);
        assertThat(result.hasEntries()).isTrue();
        assertThat(result.contextSource()).isEqualTo(PatientContextSource.CONFIGURED);
        assertThat(result.toString()).doesNotContain("secret-condition");
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Condition/");
    }

    @Test
    void emptySearchsetIsStillASucceededSearch() {
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);

        FhirConditionSearchResult result = FhirConditionSearchResults.succeeded("oracle-health-sandbox", bundle);

        assertThat(result.outcome()).isEqualTo(FhirConditionSearchOutcome.CONDITION_SEARCH_SUCCEEDED);
        assertThat(result.hasEntries()).isFalse();
        assertThat(result.responseType()).isEqualTo("Bundle");
    }

    @Test
    void maps401ToAuthenticationRejected() {
        FhirConditionSearchResult result = FhirConditionSearchResults.fromFailure(
                "oracle-health-sandbox", FhirClientException.from(new AuthenticationException()));

        assertThat(result.outcome()).isEqualTo(FhirConditionSearchOutcome.AUTHENTICATION_REJECTED);
        assertThat(result.httpStatus()).isEqualTo(401);
        assertThat(result.dependencyCategory()).isEqualTo(FhirErrorCategory.AUTHENTICATION_ERROR);
        assertThat(result.toString()).doesNotContain("Bearer ");
    }

    @Test
    void maps403ToAuthorizationDenied() {
        FhirConditionSearchResult result = FhirConditionSearchResults.fromFailure(
                "oracle-health-sandbox", FhirClientException.from(new ForbiddenOperationException("forbidden")));

        assertThat(result.outcome()).isEqualTo(FhirConditionSearchOutcome.AUTHORIZATION_DENIED);
        assertThat(result.httpStatus()).isEqualTo(403);
        assertThat(result.dependencyCategory()).isEqualTo(FhirErrorCategory.AUTHORIZATION_ERROR);
    }

    @Test
    void mapsTimeoutAndConnectionToDependencyFailure() {
        FhirConditionSearchResult timeout = FhirConditionSearchResults.fromFailure(
                "oracle-health-sandbox",
                FhirClientException.from(new FhirClientConnectionException(
                        "timed out", new SocketTimeoutException("Read timed out"))));
        FhirConditionSearchResult connection = FhirConditionSearchResults.fromFailure(
                "oracle-health-sandbox",
                FhirClientException.from(new FhirClientConnectionException("connection refused")));
        FhirConditionSearchResult server = FhirConditionSearchResults.fromFailure(
                "oracle-health-sandbox", FhirClientException.from(new InternalErrorException("boom")));

        assertThat(timeout.outcome()).isEqualTo(FhirConditionSearchOutcome.DEPENDENCY_FAILURE);
        assertThat(timeout.dependencyCategory()).isEqualTo(FhirErrorCategory.TIMEOUT);
        assertThat(connection.dependencyCategory()).isEqualTo(FhirErrorCategory.CONNECTION_ERROR);
        assertThat(server.dependencyCategory()).isEqualTo(FhirErrorCategory.SERVER_ERROR);
        assertThat(timeout.toString()).doesNotContain("Read timed out");
    }

    @Test
    void contextNotConfiguredDoesNotClaimAClinicalRequest() {
        FhirConditionSearchResult result = FhirConditionSearchResult.contextNotConfigured("oracle-health-sandbox");

        assertThat(result.outcome()).isEqualTo(FhirConditionSearchOutcome.PATIENT_CONTEXT_NOT_CONFIGURED);
        assertThat(result.hasPatientContext()).isFalse();
        assertThat(result.httpStatus()).isNull();
    }
}
