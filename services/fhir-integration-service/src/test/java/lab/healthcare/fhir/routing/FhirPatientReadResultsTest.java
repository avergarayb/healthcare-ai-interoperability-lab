package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.patient.PatientContextSource;

import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.server.exceptions.AuthenticationException;
import ca.uhn.fhir.rest.server.exceptions.ForbiddenOperationException;
import ca.uhn.fhir.rest.server.exceptions.InternalErrorException;
import ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException;
import org.hl7.fhir.r4.model.HumanName;
import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.Test;

import java.net.SocketTimeoutException;

import static org.assertj.core.api.Assertions.assertThat;

class FhirPatientReadResultsTest {

    @Test
    void succeededRecordsResourceTypeWithoutPayload() {
        Patient patient = new Patient();
        patient.setId("lab-configured-patient");
        patient.addName(new HumanName().setFamily("SecretFamily"));

        FhirPatientReadResult result = FhirPatientReadResults.succeeded("oracle-health-sandbox", patient);

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.PATIENT_READ_SUCCEEDED);
        assertThat(result.resourceType()).isEqualTo("Patient");
        assertThat(result.responseType()).isEqualTo("Patient");
        assertThat(result.httpStatus()).isEqualTo(200);
        assertThat(result.hasPatientContext()).isTrue();
        assertThat(result.contextSource()).isEqualTo(PatientContextSource.CONFIGURED);
        assertThat(result.toString()).doesNotContain("lab-configured-patient");
        assertThat(result.toString()).doesNotContain("SecretFamily");
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Patient/");
    }

    @Test
    void maps401ToAuthenticationRejected() {
        FhirPatientReadResult result = FhirPatientReadResults.fromFailure(
                "oracle-health-sandbox", FhirClientException.from(new AuthenticationException()));

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.AUTHENTICATION_REJECTED);
        assertThat(result.httpStatus()).isEqualTo(401);
        assertThat(result.dependencyCategory()).isEqualTo(FhirErrorCategory.AUTHENTICATION_ERROR);
        assertThat(result.toString()).doesNotContain("Bearer ");
    }

    @Test
    void maps403ToAuthorizationDenied() {
        FhirPatientReadResult result = FhirPatientReadResults.fromFailure(
                "oracle-health-sandbox", FhirClientException.from(new ForbiddenOperationException("forbidden")));

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.AUTHORIZATION_DENIED);
        assertThat(result.httpStatus()).isEqualTo(403);
        assertThat(result.dependencyCategory()).isEqualTo(FhirErrorCategory.AUTHORIZATION_ERROR);
    }

    @Test
    void maps404ToPatientNotFound() {
        FhirPatientReadResult result = FhirPatientReadResults.fromFailure(
                "oracle-health-sandbox",
                FhirClientException.from(new ResourceNotFoundException("Patient/lab-configured-patient")));

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.PATIENT_NOT_FOUND);
        assertThat(result.httpStatus()).isEqualTo(404);
        assertThat(result.dependencyCategory()).isEqualTo(FhirErrorCategory.NOT_FOUND);
        assertThat(result.toString()).doesNotContain("lab-configured-patient");
        assertThat(result.detail()).doesNotContain("lab-configured-patient");
    }

    @Test
    void mapsTimeoutAndConnectionToDependencyFailure() {
        FhirPatientReadResult timeout = FhirPatientReadResults.fromFailure(
                "oracle-health-sandbox",
                FhirClientException.from(new FhirClientConnectionException(
                        "timed out", new SocketTimeoutException("Read timed out"))));
        FhirPatientReadResult connection = FhirPatientReadResults.fromFailure(
                "oracle-health-sandbox",
                FhirClientException.from(new FhirClientConnectionException("connection refused")));
        FhirPatientReadResult server = FhirPatientReadResults.fromFailure(
                "oracle-health-sandbox", FhirClientException.from(new InternalErrorException("boom")));

        assertThat(timeout.outcome()).isEqualTo(FhirPatientReadOutcome.DEPENDENCY_FAILURE);
        assertThat(timeout.dependencyCategory()).isEqualTo(FhirErrorCategory.TIMEOUT);
        assertThat(connection.dependencyCategory()).isEqualTo(FhirErrorCategory.CONNECTION_ERROR);
        assertThat(server.dependencyCategory()).isEqualTo(FhirErrorCategory.SERVER_ERROR);
        assertThat(timeout.toString()).doesNotContain("Read timed out");
    }

    @Test
    void contextNotConfiguredDoesNotClaimAPatientRequest() {
        FhirPatientReadResult result = FhirPatientReadResult.contextNotConfigured("oracle-health-sandbox");

        assertThat(result.outcome()).isEqualTo(FhirPatientReadOutcome.PATIENT_CONTEXT_NOT_CONFIGURED);
        assertThat(result.hasPatientContext()).isFalse();
        assertThat(result.httpStatus()).isNull();
    }
}
