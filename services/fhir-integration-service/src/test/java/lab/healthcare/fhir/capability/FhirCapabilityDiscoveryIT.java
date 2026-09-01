package lab.healthcare.fhir.capability;

import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.observability.FhirAuditEvent;
import lab.healthcare.fhir.observability.FhirAuditOperation;
import lab.healthcare.fhir.observability.FhirAuditOutcome;
import lab.healthcare.fhir.observability.LoggingFhirAuditRecorder;
import lab.healthcare.fhir.routing.RoutingException;
import lab.healthcare.fhir.routing.RoutingService;

import org.hl7.fhir.r4.model.CapabilityStatement;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
class FhirCapabilityDiscoveryIT {

    @Autowired
    private RoutingService routingService;

    @Autowired
    private FhirService fhirService;

    @Autowired
    private LoggingFhirAuditRecorder auditRecorder;

    @Test
    void discoversLocalHapiCapabilitiesWithoutAssumingEveryR4Resource() {
        FhirServerCapabilities capabilities = routingService.discoverCapabilities("local-hapi", "cap-hapi");

        assertThat(capabilities.destination()).isEqualTo("local-hapi");
        assertThat(capabilities.fhirVersion()).isEqualTo("4.0.1");
        assertThat(capabilities.softwareName()).contains("HAPI");
        assertThat(capabilities.implementationUrl()).contains("localhost:8080/fhir");
        assertThat(capabilities.supportsResource("Patient")).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.READ)).isTrue();
        assertThat(capabilities.supports("Patient", FhirInteraction.SEARCH_TYPE)).isTrue();
        assertThat(capabilities.supportsResource("DefinitelyNotAFhirResource")).isFalse();

        CapabilityStatement raw = fhirService.retrieveCapabilityStatement();
        assertThat(raw.getFhirVersion().toCode()).isEqualTo(capabilities.fhirVersion());
        assertThat(raw.getSoftware().getName()).isEqualTo(capabilities.softwareName());

        FhirAuditEvent event = auditRecorder.recorded().stream()
                .filter(item -> "cap-hapi".equals(item.context().correlationId()))
                .reduce((first, second) -> second)
                .orElseThrow();
        assertThat(event.outcome()).isEqualTo(FhirAuditOutcome.SUCCESS);
        assertThat(event.context().operation()).isEqualTo(FhirAuditOperation.CAPABILITY_DISCOVERY);
        assertThat(event.context().resourceType()).isEqualTo("CapabilityStatement");
        assertThat(event.toLogLine()).doesNotContain("\"resourceType\"");
        assertThat(event.toLogLine()).doesNotContain("access_token");
        assertThat(event.toLogLine()).doesNotContain("client_secret");
    }

    @Test
    void unknownDestinationRemainsRoutingValidationError() {
        assertThatThrownBy(() -> routingService.discoverCapabilities("does-not-exist", "cap-missing"))
                .isInstanceOf(RoutingException.class)
                .hasMessageContaining("does-not-exist")
                .extracting(ex -> ((RoutingException) ex).category())
                .isEqualTo(FhirErrorCategory.VALIDATION_ERROR);
    }
}
