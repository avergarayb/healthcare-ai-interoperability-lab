package lab.healthcare.fhir.federation;

import lab.healthcare.fhir.clinicalread.minihis.MiniHisClinicalSource;
import lab.healthcare.fhir.clinicalread.minilis.MiniLisClinicalSource;
import lab.healthcare.fhir.federation.audit.FederationSecurityAudit;
import lab.healthcare.fhir.federation.audit.FederationSecurityAuditRecorder;
import lab.healthcare.fhir.federation.audit.SqliteFederationSecurityAuditRecorder;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.nio.file.Path;

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
    FederationSecurityAuditRecorder federationSecurityAuditRecorder(FederationProperties properties) {
        String configured = properties.getSecurityAudit().getStorePath();
        Path path = configured == null || configured.isBlank()
                ? Path.of(System.getProperty("java.io.tmpdir"), "healthcare-lab-federation", "security-audit.sqlite")
                : Path.of(configured);
        return new SqliteFederationSecurityAuditRecorder(path);
    }

    @Bean
    FederationSecurityAudit federationSecurityAudit(FederationSecurityAuditRecorder recorder) {
        return new FederationSecurityAudit(recorder);
    }

}
