package lab.healthcare.fhir.jurisdiction;

import lab.healthcare.fhir.federation.ClinicalConnector;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties(JurisdictionLabProperties.class)
public class JurisdictionLabConfiguration {

    @Bean
    @ConditionalOnProperty(prefix = "jurisdiction-lab", name = "enabled", havingValue = "true")
    ClinicalConnector jurisdictionLabConnector(JurisdictionLabProperties properties) {
        return new JurisdictionLabConnector(JurisdictionProfile.require(properties.getProfile()));
    }
}
