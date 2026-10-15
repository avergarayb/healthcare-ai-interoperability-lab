package lab.healthcare.fhir.clinicalread.web;

import lab.healthcare.fhir.modelboundary.ModelBoundaryServiceTokenSettings;

import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;

@Configuration
public class ClinicalReadAuthConfiguration {

    @Bean
    public FilterRegistrationBean<ClinicalReadServiceAuthFilter> clinicalReadServiceAuthFilter(
            ModelBoundaryServiceTokenSettings settings) {
        FilterRegistrationBean<ClinicalReadServiceAuthFilter> registration = new FilterRegistrationBean<>();
        registration.setFilter(new ClinicalReadServiceAuthFilter(settings));
        registration.addUrlPatterns("/api/clinical-read/v1/*");
        registration.setName("clinicalReadServiceAuthFilter");
        registration.setOrder(Ordered.HIGHEST_PRECEDENCE);
        return registration;
    }
}
