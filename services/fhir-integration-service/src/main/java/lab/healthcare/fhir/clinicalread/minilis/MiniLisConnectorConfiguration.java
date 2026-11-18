package lab.healthcare.fhir.clinicalread.minilis;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;

@Configuration
@EnableConfigurationProperties(MiniLisConnectionProperties.class)
public class MiniLisConnectorConfiguration {

    @Bean
    MiniLisClinicalSource miniLisClinicalSource(
            MiniLisConnectionProperties properties, ObjectMapper json, Environment environment) {
        boolean containerNetwork = Boolean.parseBoolean(
                environment.getProperty("clinical-read.mini-lis.container-network", "false"));
        MiniLisClient client = new MiniLisClient(
                properties.baseUrl(),
                properties.serviceToken(),
                properties.connectTimeout(),
                properties.readTimeout(),
                json,
                containerNetwork);
        return new MiniLisRestSource(client, json);
    }
}
