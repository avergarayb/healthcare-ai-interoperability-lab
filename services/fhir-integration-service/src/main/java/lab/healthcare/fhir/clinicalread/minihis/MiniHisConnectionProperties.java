package lab.healthcare.fhir.clinicalread.minihis;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

@ConfigurationProperties(prefix = "clinical-read.mini-his")
public record MiniHisConnectionProperties(String baseUrl, Duration connectTimeout, Duration readTimeout) {

    public MiniHisConnectionProperties {
        if (baseUrl == null || baseUrl.isBlank()) {
            baseUrl = "http://127.0.0.1:8095";
        }
        if (connectTimeout == null) {
            connectTimeout = Duration.ofSeconds(2);
        }
        if (readTimeout == null) {
            readTimeout = Duration.ofSeconds(5);
        }
    }
}
