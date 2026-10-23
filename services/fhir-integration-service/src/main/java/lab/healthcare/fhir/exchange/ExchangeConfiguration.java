package lab.healthcare.fhir.exchange;

import com.fasterxml.jackson.databind.ObjectMapper;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

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
    @Primary
    OrderDestination miniLisOrderDestination(ExchangeProperties properties, ObjectMapper json, ExchangeStore store) {
        ExchangeProperties.Connector connector = properties.getConnectors().get("mini-lis");
        if (connector == null) {
            connector = new ExchangeProperties.Connector();
        }
        if ("hl7v2".equalsIgnoreCase(connector.getProtocol())) {
            return new MiniLisHl7ExchangeConnector(
                    connector.getHl7(),
                    connector.getHl7().getHost(),
                    connector.getHl7().getPort(),
                    connector.getHl7().getSharedSecret(),
                    connector.getConnectTimeout(),
                    connector.getReadTimeout(),
                    store,
                    json);
        }
        if (connector.getBaseUrl() == null || connector.getBaseUrl().isBlank()) {
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
    ResultSource miniLisResultSource(OrderDestination miniLisOrderDestination) {
        if (!(miniLisOrderDestination instanceof ResultSource source)) {
            throw new IllegalStateException("Mini LIS connector does not provide results");
        }
        return new ResultSource() {
            @Override
            public String systemKey() {
                return source.systemKey();
            }

            @Override
            public DestinationReport read(String destinationOrderId) {
                return source.read(destinationOrderId);
            }
        };
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
