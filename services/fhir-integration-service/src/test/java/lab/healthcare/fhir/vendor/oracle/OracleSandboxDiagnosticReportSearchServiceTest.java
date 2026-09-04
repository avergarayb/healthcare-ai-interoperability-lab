package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.connectivity.FhirEndpointConnectivityVerifier;
import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.routing.FhirDiagnosticReportSearchOutcome;
import lab.healthcare.fhir.routing.FhirDiagnosticReportSearchResult;
import lab.healthcare.fhir.routing.RoutingService;
import lab.healthcare.fhir.server.FhirServersProperties;

import ca.uhn.fhir.rest.server.exceptions.AuthenticationException;
import ca.uhn.fhir.rest.server.exceptions.ForbiddenOperationException;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.DiagnosticReport;
import org.hl7.fhir.r4.model.Enumerations;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class OracleSandboxDiagnosticReportSearchServiceTest {

    private static final Clock CLOCK = Clock.fixed(Instant.parse("2026-09-03T18:00:00Z"), ZoneOffset.UTC);
    private static final String SECRET = "oracle-live-access-token";
    private static final String PATIENT_ID = "lab-configured-patient";

    @Mock
    private FhirEndpointConnectivityVerifier verifier;

    @Mock
    private OracleSandboxAuthenticationService authenticationService;

    @Mock
    private OracleSandboxCapabilityDiscoveryService capabilityDiscovery;

    @Mock
    private RoutingService routingService;

    @Test
    void disabledProfileDoesNotCallOracle() {
        FhirDiagnosticReportSearchResult result =
                service().searchDiagnosticReports(OracleHealthIntegrationProfileTest.completePublicPkce());

        assertThat(result.outcome()).isEqualTo(FhirDiagnosticReportSearchOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.toString()).doesNotContain(SECRET);
        verify(authenticationService, never()).issuedProviderIfPresent();
        verify(capabilityDiscovery, never()).discover(any());
        verify(routingService, never()).searchDiagnosticReports(any(), any(), any());
        verify(verifier, never()).verify(any());
    }

    @Test
    void missingPatientIdIsContextNotConfiguredWithoutHttp() {
        FhirDiagnosticReportSearchResult result =
                service().searchDiagnosticReports(OracleHealthIntegrationProfileTest.completePublicPkceEnabled());

        assertThat(result.outcome()).isEqualTo(FhirDiagnosticReportSearchOutcome.PATIENT_CONTEXT_NOT_CONFIGURED);
        assertThat(result.hasPatientContext()).isFalse();
        verify(authenticationService, never()).issuedProviderIfPresent();
        verify(capabilityDiscovery, never()).discover(any());
        verify(routingService, never()).searchDiagnosticReports(any(), any(), any());
    }

    @Test
    void missingTokenIsAuthenticationRequiredWithoutHttp() {
        when(authenticationService.issuedProviderIfPresent()).thenReturn(Optional.empty());

        FhirDiagnosticReportSearchResult result = service().searchDiagnosticReports(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirDiagnosticReportSearchOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.detail()).contains("No usable access token");
        verify(capabilityDiscovery, never()).discover(any());
        verify(routingService, never()).searchDiagnosticReports(any(), any(), any());
    }

    @Test
    void expiredTokenIsAuthenticationRequiredWithoutHttp() {
        when(authenticationService.issuedProviderIfPresent())
                .thenReturn(Optional.of(new IssuedAccessTokenProvider(
                        new AccessToken(SECRET, Instant.parse("2026-09-03T17:00:00Z")))));

        FhirDiagnosticReportSearchResult result = service().searchDiagnosticReports(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirDiagnosticReportSearchOutcome.AUTHENTICATION_REQUIRED);
        assertThat(result.detail()).contains("expired");
        assertThat(result.toString()).doesNotContain(SECRET);
        verify(capabilityDiscovery, never()).discover(any());
        verify(routingService, never()).searchDiagnosticReports(any(), any(), any());
    }

    @Test
    void missingDiagnosticReportCapabilityIsUnsupportedWithoutSearch() {
        usableToken();
        when(capabilityDiscovery.discover(any())).thenReturn(patientReadOnly());

        FhirDiagnosticReportSearchResult result = service().searchDiagnosticReports(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirDiagnosticReportSearchOutcome.CAPABILITY_UNSUPPORTED);
        verify(routingService, never()).searchDiagnosticReports(any(), any(), any());
    }

    @Test
    void validTokenContextAndCapabilityExecuteGenericSearch() {
        usableToken();
        when(capabilityDiscovery.discover(any())).thenReturn(diagnosticReportSearchSupported());
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.SEARCHSET);
        DiagnosticReport report = new DiagnosticReport();
        report.setId("secret-diagnostic-report");
        bundle.addEntry().setResource(report);
        when(routingService.searchDiagnosticReports(any(), any(), eq(PATIENT_ID))).thenReturn(bundle);

        FhirDiagnosticReportSearchResult result = service().searchDiagnosticReports(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirDiagnosticReportSearchOutcome.DIAGNOSTIC_REPORT_SEARCH_SUCCEEDED);
        assertThat(result.responseType()).isEqualTo("Bundle");
        assertThat(result.hasEntries()).isTrue();
        assertThat(result.toString()).doesNotContain(SECRET);
        assertThat(result.toString()).doesNotContain(PATIENT_ID);
        assertThat(result.toString()).doesNotContain("secret-diagnostic-report");
        verify(routingService).searchDiagnosticReports(any(), any(), eq(PATIENT_ID));
    }

    @Test
    void http401IsAuthenticationRejected() {
        usableToken();
        when(capabilityDiscovery.discover(any())).thenReturn(diagnosticReportSearchSupported());
        when(routingService.searchDiagnosticReports(any(), any(), any()))
                .thenThrow(FhirClientException.from(new AuthenticationException()));

        FhirDiagnosticReportSearchResult result = service().searchDiagnosticReports(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirDiagnosticReportSearchOutcome.AUTHENTICATION_REJECTED);
        assertThat(result.httpStatus()).isEqualTo(401);
        assertThat(result.toString()).doesNotContain(SECRET);
    }

    @Test
    void http403IsAuthorizationDenied() {
        usableToken();
        when(capabilityDiscovery.discover(any())).thenReturn(diagnosticReportSearchSupported());
        when(routingService.searchDiagnosticReports(any(), any(), any()))
                .thenThrow(FhirClientException.from(new ForbiddenOperationException("forbidden")));

        FhirDiagnosticReportSearchResult result = service().searchDiagnosticReports(enabledWithPatient(PATIENT_ID));

        assertThat(result.outcome()).isEqualTo(FhirDiagnosticReportSearchOutcome.AUTHORIZATION_DENIED);
        assertThat(result.dependencyCategory()).isEqualTo(FhirErrorCategory.AUTHORIZATION_ERROR);
    }

    private void usableToken() {
        when(authenticationService.issuedProviderIfPresent())
                .thenReturn(Optional.of(new IssuedAccessTokenProvider(
                        new AccessToken(SECRET, Instant.parse("2026-09-03T19:00:00Z")))));
    }

    private OracleSandboxDiagnosticReportSearchService service() {
        return new OracleSandboxDiagnosticReportSearchService(
                new OracleSandboxReadinessService(new OracleSandboxProfileValidator(), verifier),
                authenticationService,
                capabilityDiscovery,
                routingService,
                CLOCK);
    }

    private static OracleHealthIntegrationProfile enabledWithPatient(String patientId) {
        return OracleHealthIntegrationProfile.from(
                OracleHealthIntegrationProfileTest.oracleServer(true, OracleHealthIntegrationProfileTest.smartAuth()),
                new FhirServersProperties.VendorIntegrationSettings(
                        "SANDBOX", "STANDALONE", "PATIENT", "PUBLIC_PKCE", patientId));
    }

    private static FhirServerCapabilities patientReadOnly() {
        CapabilityStatement statement = new CapabilityStatement();
        statement.setFhirVersion(Enumerations.FHIRVersion._4_0_1);
        CapabilityStatement.CapabilityStatementRestResourceComponent patient = statement.addRest().addResource();
        patient.setType("Patient");
        patient.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.READ);
        return new lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService()
                .interpret("oracle-health-sandbox", statement);
    }

    private static FhirServerCapabilities diagnosticReportSearchSupported() {
        CapabilityStatement statement = new CapabilityStatement();
        statement.setFhirVersion(Enumerations.FHIRVersion._4_0_1);
        CapabilityStatement.CapabilityStatementRestResourceComponent report = statement.addRest().addResource();
        report.setType("DiagnosticReport");
        report.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.SEARCHTYPE);
        return new lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService()
                .interpret("oracle-health-sandbox", statement);
    }
}
