package lab.healthcare.fhir.interop;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties(InteropSourcesProperties.class)
public class InteropConfiguration {
}
