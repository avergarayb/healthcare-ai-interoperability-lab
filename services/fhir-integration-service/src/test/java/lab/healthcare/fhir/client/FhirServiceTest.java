package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.server.exceptions.InternalErrorException;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.Enumerations;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Answers;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class FhirServiceTest {

    @Mock(answer = Answers.RETURNS_DEEP_STUBS)
    private IGenericClient fhirClient;

    @InjectMocks
    private FhirService fhirService;

    @Test
    void retrieveCapabilityStatementReturnsServerMetadata() {
        CapabilityStatement expected = new CapabilityStatement();
        expected.setFhirVersion(Enumerations.FHIRVersion._4_0_1);
        when(fhirClient.capabilities().ofType(CapabilityStatement.class).execute()).thenReturn(expected);

        CapabilityStatement actual = fhirService.retrieveCapabilityStatement();

        assertThat(actual).isSameAs(expected);
        assertThat(actual.getFhirVersion()).isEqualTo(Enumerations.FHIRVersion._4_0_1);
    }

    @Test
    void retrieveCapabilityStatementDoesNotSwallowConnectionErrors() {
        when(fhirClient.capabilities().ofType(CapabilityStatement.class).execute())
                .thenThrow(new FhirClientConnectionException("connection refused"));

        assertThatThrownBy(() -> fhirService.retrieveCapabilityStatement())
                .isInstanceOf(FhirClientException.class)
                .hasMessageContaining("Unable to connect")
                .hasCauseInstanceOf(FhirClientConnectionException.class);
    }

    @Test
    void retrieveCapabilityStatementDoesNotSwallowServerErrors() {
        when(fhirClient.capabilities().ofType(CapabilityStatement.class).execute())
                .thenThrow(new InternalErrorException("server error"));

        assertThatThrownBy(() -> fhirService.retrieveCapabilityStatement())
                .isInstanceOf(FhirClientException.class)
                .hasMessageContaining("returned an error")
                .hasCauseInstanceOf(InternalErrorException.class);
    }
}
