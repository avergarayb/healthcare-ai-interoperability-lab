package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.patient.PatientContextSource;

import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.server.exceptions.AuthenticationException;
import ca.uhn.fhir.rest.server.exceptions.ForbiddenOperationException;
import ca.uhn.fhir.rest.server.exceptions.InternalErrorException;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.DiagnosticReport;
import org.junit.jupiter.api.Test;

import java.net.SocketTimeoutException;

import static org.assertj.core.api.Assertions.assertThat;

class FhirDiagnosticReportSearchResultsTest {

    @Test
    void succeededRecordsBundleMetadataWithoutPayload() {
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);
        DiagnosticReport report = new DiagnosticReport();
        report.setId("secret-diagnostic-report");
        bundle.addEntry().setResource(report);

        FhirDiagnosticReportSearchResult result =
                FhirDiagnosticReportSearchResults.succeeded("oracle-health-sandbox", bundle);

        assertThat(result.outcome()).isEqualTo(FhirDiagnosticReportSearchOutcome.DIAGNOSTIC_REPORT_SEARCH_SUCCEEDED);
        assertThat(result.resourceType()).isEqualTo("DiagnosticReport");
        assertThat(result.responseType()).isEqualTo("Bundle");
        assertThat(result.httpStatus()).isEqualTo(200);
        assertThat(result.hasEntries()).isTrue();
        assertThat(result.contextSource()).isEqualTo(PatientContextSource.CONFIGURED);
        assertThat(result.toString()).doesNotContain("secret-diagnostic-report");
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("DiagnosticReport/");
    }

    @Test
    void emptySearchsetIsStillASucceededSearch() {
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);

        FhirDiagnosticReportSearchResult result =
                FhirDiagnosticReportSearchResults.succeeded("oracle-health-sandbox", bundle);

        assertThat(result.outcome()).isEqualTo(FhirDiagnosticReportSearchOutcome.DIAGNOSTIC_REPORT_SEARCH_SUCCEEDED);
        assertThat(result.hasEntries()).isFalse();
        assertThat(result.responseType()).isEqualTo("Bundle");
    }

    @Test
    void maps401ToAuthenticationRejected() {
        FhirDiagnosticReportSearchResult result = FhirDiagnosticReportSearchResults.fromFailure(
                "oracle-health-sandbox", FhirClientException.from(new AuthenticationException()));

        assertThat(result.outcome()).isEqualTo(FhirDiagnosticReportSearchOutcome.AUTHENTICATION_REJECTED);
        assertThat(result.httpStatus()).isEqualTo(401);
        assertThat(result.dependencyCategory()).isEqualTo(FhirErrorCategory.AUTHENTICATION_ERROR);
        assertThat(result.toString()).doesNotContain("Bearer ");
    }

    @Test
    void maps403ToAuthorizationDenied() {
        FhirDiagnosticReportSearchResult result = FhirDiagnosticReportSearchResults.fromFailure(
                "oracle-health-sandbox", FhirClientException.from(new ForbiddenOperationException("forbidden")));

        assertThat(result.outcome()).isEqualTo(FhirDiagnosticReportSearchOutcome.AUTHORIZATION_DENIED);
        assertThat(result.httpStatus()).isEqualTo(403);
        assertThat(result.dependencyCategory()).isEqualTo(FhirErrorCategory.AUTHORIZATION_ERROR);
    }

    @Test
    void mapsTimeoutAndConnectionToDependencyFailure() {
        FhirDiagnosticReportSearchResult timeout = FhirDiagnosticReportSearchResults.fromFailure(
                "oracle-health-sandbox",
                FhirClientException.from(new FhirClientConnectionException(
                        "timed out", new SocketTimeoutException("Read timed out"))));
        FhirDiagnosticReportSearchResult connection = FhirDiagnosticReportSearchResults.fromFailure(
                "oracle-health-sandbox",
                FhirClientException.from(new FhirClientConnectionException("connection refused")));
        FhirDiagnosticReportSearchResult server = FhirDiagnosticReportSearchResults.fromFailure(
                "oracle-health-sandbox", FhirClientException.from(new InternalErrorException("boom")));

        assertThat(timeout.outcome()).isEqualTo(FhirDiagnosticReportSearchOutcome.DEPENDENCY_FAILURE);
        assertThat(timeout.dependencyCategory()).isEqualTo(FhirErrorCategory.TIMEOUT);
        assertThat(connection.dependencyCategory()).isEqualTo(FhirErrorCategory.CONNECTION_ERROR);
        assertThat(server.dependencyCategory()).isEqualTo(FhirErrorCategory.SERVER_ERROR);
        assertThat(timeout.toString()).doesNotContain("Read timed out");
    }

    @Test
    void contextNotConfiguredDoesNotClaimAClinicalRequest() {
        FhirDiagnosticReportSearchResult result =
                FhirDiagnosticReportSearchResult.contextNotConfigured("oracle-health-sandbox");

        assertThat(result.outcome()).isEqualTo(FhirDiagnosticReportSearchOutcome.PATIENT_CONTEXT_NOT_CONFIGURED);
        assertThat(result.hasPatientContext()).isFalse();
        assertThat(result.httpStatus()).isNull();
    }
}
