package lab.healthcare.fhir.exception;

import lab.healthcare.fhir.auth.oauth2.OAuth2TokenException;

import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.server.exceptions.AuthenticationException;
import ca.uhn.fhir.rest.server.exceptions.ForbiddenOperationException;
import ca.uhn.fhir.rest.server.exceptions.InternalErrorException;
import ca.uhn.fhir.rest.server.exceptions.InvalidRequestException;
import ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException;
import ca.uhn.fhir.rest.server.exceptions.ResourceVersionConflictException;
import ca.uhn.fhir.rest.server.exceptions.UnclassifiedServerFailureException;
import org.junit.jupiter.api.Test;

import java.net.ConnectException;
import java.net.SocketTimeoutException;

import static org.assertj.core.api.Assertions.assertThat;

class FhirErrorClassifierTest {

    @Test
    void mapsHttpStatusesToBoundedCategories() {
        assertThat(FhirErrorClassifier.categoryForStatus(400)).isEqualTo(FhirErrorCategory.VALIDATION_ERROR);
        assertThat(FhirErrorClassifier.categoryForStatus(401)).isEqualTo(FhirErrorCategory.AUTHENTICATION_ERROR);
        assertThat(FhirErrorClassifier.categoryForStatus(403)).isEqualTo(FhirErrorCategory.AUTHORIZATION_ERROR);
        assertThat(FhirErrorClassifier.categoryForStatus(404)).isEqualTo(FhirErrorCategory.NOT_FOUND);
        assertThat(FhirErrorClassifier.categoryForStatus(409)).isEqualTo(FhirErrorCategory.CONFLICT);
        assertThat(FhirErrorClassifier.categoryForStatus(408)).isEqualTo(FhirErrorCategory.TIMEOUT);
        assertThat(FhirErrorClassifier.categoryForStatus(429)).isEqualTo(FhirErrorCategory.SERVER_ERROR);
        assertThat(FhirErrorClassifier.categoryForStatus(500)).isEqualTo(FhirErrorCategory.SERVER_ERROR);
        assertThat(FhirErrorClassifier.categoryForStatus(503)).isEqualTo(FhirErrorCategory.SERVER_ERROR);
    }

    @Test
    void classifiesHapiExceptionsByStatus() {
        assertCategory(new InvalidRequestException("bad request"), FhirErrorCategory.VALIDATION_ERROR, 400);
        assertCategory(new AuthenticationException(), FhirErrorCategory.AUTHENTICATION_ERROR, 401);
        assertCategory(new ForbiddenOperationException("forbidden"), FhirErrorCategory.AUTHORIZATION_ERROR, 403);
        assertCategory(new ResourceNotFoundException("Patient/missing"), FhirErrorCategory.NOT_FOUND, 404);
        assertCategory(new ResourceVersionConflictException("conflict"), FhirErrorCategory.CONFLICT, 409);
        assertCategory(new InternalErrorException("boom"), FhirErrorCategory.SERVER_ERROR, 500);
        assertCategory(new UnclassifiedServerFailureException(503, "unavailable"), FhirErrorCategory.SERVER_ERROR, 503);
    }

    @Test
    void classifiesTimeoutSeparatelyFromConnectionFailure() {
        FhirErrorDetails timeout = FhirErrorClassifier.classify(
                new FhirClientConnectionException("timed out", new SocketTimeoutException("Read timed out")));
        FhirErrorDetails connection = FhirErrorClassifier.classify(
                new FhirClientConnectionException("connection refused", new ConnectException("Connection refused")));

        assertThat(timeout.category()).isEqualTo(FhirErrorCategory.TIMEOUT);
        assertThat(timeout.message()).isEqualTo("FHIR request timed out");
        assertThat(connection.category()).isEqualTo(FhirErrorCategory.CONNECTION_ERROR);
        assertThat(connection.message()).isEqualTo("FHIR connection failed");
        assertThat(timeout.message()).doesNotContain("Read timed out");
        assertThat(connection.message()).doesNotContain("Connection refused");
    }

    @Test
    void classifiesOAuthFailuresAsAuthenticationErrors() {
        FhirErrorDetails details = FhirErrorClassifier.classify(
                new OAuth2TokenException("OAuth token acquisition failed: HTTP 401 invalid_client"));

        assertThat(details.category()).isEqualTo(FhirErrorCategory.AUTHENTICATION_ERROR);
        assertThat(details.message()).isEqualTo("FHIR authentication failed");
        assertThat(details.message()).doesNotContain("invalid_client");
        assertThat(details.toLogLine()).doesNotContain("access_token");
        assertThat(details.toLogLine()).doesNotContain("client_secret");
    }

    @Test
    void unknownExceptionsBecomeUnknownWithoutLeakingPayloads() {
        FhirErrorDetails details = FhirErrorClassifier.classify(new IllegalStateException("Patient JSON {\"name\":\"Garcia\"}"));

        assertThat(details.category()).isEqualTo(FhirErrorCategory.UNKNOWN);
        assertThat(details.message()).isEqualTo("FHIR integration failed");
        assertThat(details.message()).doesNotContain("Garcia");
        assertThat(details.toLogLine()).doesNotContain("Garcia");
        assertThat(details.toLogLine()).doesNotContain("{");
    }

    private static void assertCategory(Throwable throwable, FhirErrorCategory category, int status) {
        FhirErrorDetails details = FhirErrorClassifier.classify(throwable);
        assertThat(details.category()).isEqualTo(category);
        assertThat(details.status()).isEqualTo(status);
        assertThat(details.message()).isEqualTo(category.safeMessage());
    }
}
