package lab.healthcare.fhir.externalfhir;

import lab.healthcare.fhir.federation.ClinicalConnector;
import lab.healthcare.fhir.federation.FederationProperties;
import lab.healthcare.fhir.federation.FederationService;
import lab.healthcare.fhir.federation.JurisdictionBinding;
import lab.healthcare.fhir.federation.audit.FederationSecurityAudit;
import lab.healthcare.fhir.jurisdiction.JurisdictionLabProperties;
import lab.healthcare.fhir.jurisdiction.JurisdictionProfile;
import lab.healthcare.fhir.exchange.ExchangeStore;
import lab.healthcare.fhir.interop.SourceRegistry;

import com.fasterxml.jackson.databind.ObjectMapper;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Wires the external reader only when external-fhir.enabled is true.
 * The checked-in grant list stays unchanged.
 */
@Configuration
@EnableConfigurationProperties(ExternalFhirProperties.class)
public class ExternalFhirConfiguration {

    @Bean
    @ConditionalOnProperty(prefix = "external-fhir", name = "enabled", havingValue = "true")
    ExternalFhirAudit externalFhirAudit(ExternalFhirProperties properties) {
        properties.requireClosed();
        return new ExternalFhirAudit(path(properties.getAuditStorePath(), "request-audit.sqlite"));
    }

    @Bean
    @ConditionalOnProperty(prefix = "external-fhir", name = "enabled", havingValue = "true")
    ExternalPatientLinkStore externalPatientLinkStore(ExternalFhirProperties properties) {
        properties.requireClosed();
        return new ExternalPatientLinkStore(
                path(properties.getLinkStorePath(), "patient-link.sqlite"), properties.getSourceKey());
    }

    @Bean
    @ConditionalOnProperty(prefix = "external-fhir", name = "enabled", havingValue = "true")
    ExternalFhirClient externalFhirClient(
            ExternalFhirProperties properties, ExternalFhirAudit audit, ObjectMapper json) {
        return new ExternalFhirClient(properties, audit, json);
    }

    @Bean
    @ConditionalOnProperty(prefix = "external-fhir", name = "enabled", havingValue = "true")
    ClinicalConnector smartSandboxConnector(ExternalFhirClient client) {
        return new ExternalFhirConnector(client);
    }

    @Bean
    @Primary
    FederationService externalAwareFederationService(
            SourceRegistry registry,
            ExchangeStore store,
            List<ClinicalConnector> connectors,
            FederationProperties federation,
            ObjectMapper json,
            FederationSecurityAudit securityAudit,
            org.springframework.beans.factory.ObjectProvider<ExternalFhirProperties> external,
            org.springframework.beans.factory.ObjectProvider<ExternalPatientLinkStore> links,
            org.springframework.beans.factory.ObjectProvider<JurisdictionLabProperties> jurisdiction) {
        ExternalFhirProperties properties = external.getIfAvailable();
        ExternalPatientLinkStore linkStore = links.getIfAvailable();
        JurisdictionLabProperties jurisdictionProperties = jurisdiction.getIfAvailable();
        SourceRegistry effective = registry;
        Set<String> explicit = new java.util.LinkedHashSet<>();
        Map<String, JurisdictionBinding> bindings = Map.of();
        if (properties != null && properties.isEnabled() && linkStore != null) {
            properties.requireClosed();
            effective = registry.withAdditional(properties.descriptor());
            grant(federation, properties.getCallerSystem(), properties.getSourceKey());
            explicit.add(properties.getSourceKey());
        }
        if (jurisdictionProperties != null && jurisdictionProperties.isEnabled()) {
            JurisdictionProfile profile = JurisdictionProfile.require(jurisdictionProperties.getProfile());
            effective = effective.withAdditional(profile.descriptor());
            grant(federation, "mini-his", profile.sourceKey());
            explicit.add(profile.sourceKey());
            bindings = Map.of(profile.sourceKey(), profile.binding());
        }
        return new FederationService(
                effective, store, connectors, federation, json, securityAudit, linkStore,
                Set.copyOf(explicit), bindings);
    }

    private static void grant(FederationProperties federation, String caller, String sourceKey) {
        List<String> grant = new ArrayList<>(federation.getGrants().getOrDefault(caller, List.of()));
        if (!grant.contains(sourceKey)) {
            grant.add(sourceKey);
            federation.getGrants().put(caller, List.copyOf(grant));
        }
    }

    private static Path path(String configured, String name) {
        if (configured == null || configured.isBlank()) {
            return Path.of(System.getProperty("java.io.tmpdir"), "healthcare-lab-external-fhir", name);
        }
        return Path.of(configured);
    }
}
