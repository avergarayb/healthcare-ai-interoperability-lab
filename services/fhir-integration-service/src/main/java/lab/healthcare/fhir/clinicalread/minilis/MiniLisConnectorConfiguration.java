package lab.healthcare.fhir.clinicalread.minilis;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties(MiniLisConnectionProperties.class)
public class MiniLisConnectorConfiguration {

    @Bean
    MiniLisClinicalSource miniLisClinicalSource(MiniLisConnectionProperties properties, ObjectMapper json) {
        MiniLisClient client = new MiniLisClient(
                properties.baseUrl(),
                properties.serviceToken(),
                properties.connectTimeout(),
                properties.readTimeout(),
                json);
        return new MiniLisRestSource(client, json);
    }
}
