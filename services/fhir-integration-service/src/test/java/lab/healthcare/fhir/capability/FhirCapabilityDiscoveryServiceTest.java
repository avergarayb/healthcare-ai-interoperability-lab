package lab.healthcare.fhir.capability;

import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.Enumerations;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Answers;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
public class FhirCapabilityDiscoveryServiceTest {

    private final FhirCapabilityDiscoveryService discovery = new FhirCapabilityDiscoveryService();

    @Mock(answer = Answers.RETURNS_DEEP_STUBS)
    private IGenericClient fhirClient;

    @Test
    void interpretsCapabilityStatementIntoInternalModel() {
        FhirServerCapabilities capabilities = discovery.interpret("local-hapi", sampleStatement());

        assertThat(capabilities.destination()).isEqualTo("local-hapi");
        assertThat(capabilities.fhirVersion()).isEqualTo("4.0.1");
        assertThat(capabilities.softwareName()).isEqualTo("HAPI FHIR Server");
        assertThat(capabilities.implementationUrl()).isEqualTo("http://localhost:8080/fhir");
        assertThat(capabilities.supportsResource("Patient")).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.READ)).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.SEARCH_TYPE)).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.CREATE)).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.UPDATE)).isFalse();
        assertThat(capabilities.supportsResource("Account")).isFalse();
        assertThat(capabilities.supports("Observation", FhirInteraction.READ)).isTrue();
        assertThat(capabilities.supports("Observation", FhirInteraction.SEARCH_TYPE)).isFalse();
    }

    @Test
    void unknownInteractionsAreIgnored() {
        CapabilityStatement statement = new CapabilityStatement();
        statement.setFhirVersion(Enumerations.FHIRVersion._4_0_1);
        CapabilityStatement.CapabilityStatementRestResourceComponent patient =
                statement.addRest().addResource();
        patient.setType("Patient");
        patient.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.READ);
        patient.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.VREAD);

        FhirServerCapabilities capabilities = discovery.interpret("local-hapi", statement);

        assertThat(capabilities.supports("Patient", FhirInteraction.READ)).isTrue();
        assertThat(capabilities.resource("Patient").orElseThrow().interactions())
                .containsExactly(FhirInteraction.READ);
    }

    @Test
    void missingVersionIsInterpretationFailure() {
        assertThatThrownBy(() -> discovery.interpret("local-hapi", new CapabilityStatement()))
                .isInstanceOf(FhirCapabilityException.class)
                .hasMessageContaining("fhirVersion")
                .hasMessageNotContaining("access_token")
                .hasMessageNotContaining("client_secret");
    }

    @Test
    void missingStatementIsInterpretationFailure() {
        assertThatThrownBy(() -> discovery.interpret("local-hapi", null))
                .isInstanceOf(FhirCapabilityException.class)
                .hasMessageContaining("missing");
    }

    @Test
    void transportFailureStaysFhirClientException() {
        when(fhirClient.capabilities().ofType(CapabilityStatement.class).execute())
                .thenThrow(new FhirClientConnectionException("connection refused"));

        assertThatThrownBy(() -> discovery.discover("local-hapi", fhirClient))
                .isInstanceOf(FhirClientException.class)
                .extracting(ex -> ((FhirClientException) ex).category())
                .isEqualTo(FhirErrorCategory.CONNECTION_ERROR);
    }

    @Test
    void discoverUsesClientMetadataWithoutInventingResources() {
        when(fhirClient.capabilities().ofType(CapabilityStatement.class).execute()).thenReturn(sampleStatement());

        FhirServerCapabilities capabilities = discovery.discover("local-hapi", fhirClient);

        assertThat(capabilities.supportsResource("Patient")).isTrue();
        assertThat(capabilities.supportsResource("Coverage")).isFalse();
    }

    public static CapabilityStatement sampleStatement() {
        CapabilityStatement statement = new CapabilityStatement();
        statement.setFhirVersion(Enumerations.FHIRVersion._4_0_1);
        statement.getSoftware().setName("HAPI FHIR Server");
        statement.getImplementation().setUrl("http://localhost:8080/fhir");
        CapabilityStatement.CapabilityStatementRestComponent rest = statement.addRest();
        CapabilityStatement.CapabilityStatementRestResourceComponent patient = rest.addResource();
        patient.setType("Patient");
        patient.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.READ);
        patient.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.SEARCHTYPE);
        patient.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.CREATE);
        CapabilityStatement.CapabilityStatementRestResourceComponent observation = rest.addResource();
        observation.setType("Observation");
        observation.addInteraction().setCode(CapabilityStatement.TypeRestfulInteraction.READ);
        return statement;
    }
}
