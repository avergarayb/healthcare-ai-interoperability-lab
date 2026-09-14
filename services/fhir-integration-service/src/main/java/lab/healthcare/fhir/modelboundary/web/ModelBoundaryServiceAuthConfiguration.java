package lab.healthcare.fhir.modelboundary.web;

import lab.healthcare.fhir.modelboundary.ModelBoundaryServiceTokenSettings;

import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;

@Configuration
public class ModelBoundaryServiceAuthConfiguration {

    @Bean
    public FilterRegistrationBean<ModelBoundaryServiceAuthFilter> modelBoundaryServiceAuthFilter(
            ModelBoundaryServiceTokenSettings settings) {
        FilterRegistrationBean<ModelBoundaryServiceAuthFilter> registration = new FilterRegistrationBean<>();
        registration.setFilter(new ModelBoundaryServiceAuthFilter(settings));
        registration.addUrlPatterns("/api/model-boundary/v1");
        registration.setName("modelBoundaryServiceAuthFilter");
        registration.setOrder(Ordered.HIGHEST_PRECEDENCE);
        return registration;
    }
}
