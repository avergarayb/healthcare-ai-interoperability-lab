package lab.healthcare.fhir.iam;

import java.util.List;
import lab.healthcare.fhir.exchange.ExchangeProperties;
import lab.healthcare.fhir.federation.FederationProperties;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;
import org.springframework.core.env.Environment;
import org.springframework.security.web.DefaultSecurityFilterChain;
import org.springframework.security.web.FilterChainProxy;
import org.springframework.security.web.SecurityFilterChain;

/** No @EnableWebSecurity or global starter. This proxy is registered only for the IAM GET path. */
@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(name = "iam.java.workload.lab.enabled", havingValue = "true")
class JavaOidcConfiguration {
    @Bean
    SecurityFilterChain javaOidcSecurityFilterChain(Environment environment, FederationProperties federation, ExchangeProperties exchange) {
        var boundary = new JavaOidcBoundary(environment.getProperty("IAM_JAVA_WORKLOAD_TRUST_CONFIG_PATH", ""),
                environment.getProperty("IAM_JAVA_WORKLOAD_AUDIT_DB_PATH", ""),
                List.of(federation.getSecurityAudit().getStorePath(), exchange.getStorePath()));
        return new DefaultSecurityFilterChain(JavaOidcBoundary::matches, boundary);
    }
    @Bean
    FilterRegistrationBean<FilterChainProxy> javaOidcLabFilter(SecurityFilterChain javaOidcSecurityFilterChain) {
        var registration = new FilterRegistrationBean<>(new FilterChainProxy(javaOidcSecurityFilterChain));
        registration.setName("javaOidcLabFilter");
        registration.addUrlPatterns(JavaOidcTrust.ROUTE);
        registration.setOrder(Ordered.HIGHEST_PRECEDENCE + 10);
        return registration;
    }
}
