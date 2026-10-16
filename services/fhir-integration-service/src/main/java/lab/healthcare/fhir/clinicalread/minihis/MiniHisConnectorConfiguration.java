package lab.healthcare.fhir.clinicalread.minihis;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Duration;

@Configuration
@EnableConfigurationProperties(MiniHisConnectionProperties.class)
public class MiniHisConnectorConfiguration {

    @Bean
    MiniHisClinicalSource miniHisClinicalSource(MiniHisConnectionProperties properties, ObjectMapper json) {
        Duration connect = properties.connectTimeout();
        Duration read = properties.readTimeout();
        MiniHisClient client = new MiniHisClient(properties.baseUrl(), connect, read, json);
        return new MiniHisRestSource(client, json);
    }
}
