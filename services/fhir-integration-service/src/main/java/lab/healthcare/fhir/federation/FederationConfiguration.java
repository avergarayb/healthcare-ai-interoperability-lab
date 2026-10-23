package lab.healthcare.fhir.federation;

import lab.healthcare.fhir.clinicalread.minihis.MiniHisClinicalSource;
import lab.healthcare.fhir.clinicalread.minilis.MiniLisClinicalSource;
import lab.healthcare.fhir.exchange.ExchangeStore;
import lab.healthcare.fhir.interop.SourceRegistry;

import com.fasterxml.jackson.databind.ObjectMapper;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.List;

@Configuration
@EnableConfigurationProperties(FederationProperties.class)
public class FederationConfiguration {

    @Bean
    ClinicalConnector miniHisFederationConnector(MiniHisClinicalSource source) {
        return ExistingClinicalConnectors.miniHis(source);
    }

    @Bean
    ClinicalConnector miniLisFederationConnector(MiniLisClinicalSource source) {
        return ExistingClinicalConnectors.miniLis(source);
    }

    @Bean
    FederationService federationService(
            SourceRegistry registry,
            ExchangeStore store,
            List<ClinicalConnector> connectors,
            FederationProperties properties,
            ObjectMapper json) {
        return new FederationService(registry, store, connectors, properties, json);
    }
}
