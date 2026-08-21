package lab.healthcare.fhir.client;

import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.Enumerations;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class FhirCapabilityStatementIT {

    @Autowired
    private FhirService fhirService;

    @Test
    void retrieveCapabilityStatementFromLocalHapiFhir() {
        CapabilityStatement capabilityStatement = fhirService.retrieveCapabilityStatement();

        assertThat(capabilityStatement).isNotNull();
        assertThat(capabilityStatement.getFhirVersion()).isEqualTo(Enumerations.FHIRVersion._4_0_1);
        assertThat(capabilityStatement.getFhirVersion().toCode()).isEqualTo("4.0.1");
        assertThat(capabilityStatement.getStatus()).isEqualTo(Enumerations.PublicationStatus.ACTIVE);
    }
}
