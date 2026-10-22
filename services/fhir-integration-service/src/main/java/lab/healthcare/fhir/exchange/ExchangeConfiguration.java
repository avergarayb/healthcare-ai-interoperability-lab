package lab.healthcare.fhir.exchange;

import com.fasterxml.jackson.databind.ObjectMapper;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.nio.file.Path;
import java.util.List;

@Configuration
@EnableConfigurationProperties(ExchangeProperties.class)
public class ExchangeConfiguration {

    @Bean
    ExchangeStore exchangeStore(ExchangeProperties properties) {
        String path = properties.getStorePath();
        if (path == null || path.isBlank()) {
            path = Path.of(System.getProperty("java.io.tmpdir"), "healthcare-lab-exchange", "correlation.sqlite").toString();
        }
        return new SqliteExchangeStore(Path.of(path));
    }

    @Bean
    MiniLisExchangeConnector miniLisExchangeConnector(ExchangeProperties properties, ObjectMapper json) {
        ExchangeProperties.Connector connector = properties.getConnectors().get("mini-lis");
        if (connector == null || connector.getBaseUrl() == null || connector.getBaseUrl().isBlank()) {
            connector = new ExchangeProperties.Connector();
            connector.setBaseUrl("http://127.0.0.1:8096");
        }
        return new MiniLisExchangeConnector(
                connector.getBaseUrl(),
                connector.getServiceToken(),
                connector.getConnectTimeout(),
                connector.getReadTimeout(),
                json);
    }

    @Bean
    ExchangeService exchangeService(
            lab.healthcare.fhir.interop.SourceRegistry registry,
            ExchangeStore store,
            List<OrderDestination> orderDestinations,
            List<ResultSource> resultSources,
            ObjectMapper json) {
        return new ExchangeService(registry, store, orderDestinations, resultSources, json);
    }
}
