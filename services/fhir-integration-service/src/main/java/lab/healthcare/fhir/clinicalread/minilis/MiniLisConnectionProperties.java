package lab.healthcare.fhir.clinicalread.minilis;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

@ConfigurationProperties(prefix = "clinical-read.mini-lis")
public record MiniLisConnectionProperties(
        String baseUrl,
        String serviceToken,
        Duration connectTimeout,
        Duration readTimeout) {

    public MiniLisConnectionProperties {
        if (baseUrl == null || baseUrl.isBlank()) {
            baseUrl = "http://127.0.0.1:8096";
        }
        if (serviceToken == null || serviceToken.isBlank()) {
            serviceToken = "lab-mini-lis-dev";
        }
        if (connectTimeout == null) {
            connectTimeout = Duration.ofSeconds(2);
        }
        if (readTimeout == null) {
            readTimeout = Duration.ofSeconds(5);
        }
    }
}
