package lab.healthcare.fhir.connectivity;

import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorClassifier;
import lab.healthcare.fhir.exception.FhirErrorDetails;

import org.springframework.stereotype.Component;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

/**
 * Contacts a FHIR base URL at {@code GET /metadata}. Does not read Patient,
 * interpret CapabilityStatement, or know Oracle/Epic credentials.
 */
@Component
public class FhirEndpointConnectivityVerifier {

    private static final Duration DEFAULT_TIMEOUT = Duration.ofSeconds(3);

    private final Probe probe;
    private final Duration timeout;

    public FhirEndpointConnectivityVerifier() {
        this(defaultProbe(), DEFAULT_TIMEOUT);
    }

    FhirEndpointConnectivityVerifier(Probe probe, Duration timeout) {
        if (probe == null) {
            throw new IllegalArgumentException("HTTP probe must be provided");
        }
        this.probe = probe;
        this.timeout = timeout == null ? DEFAULT_TIMEOUT : timeout;
    }

    public FhirConnectivityStatus verify(String fhirBaseUrl) {
        URI metadata;
        try {
            metadata = metadataUri(fhirBaseUrl);
        } catch (IllegalArgumentException ex) {
            return FhirConnectivityStatus.unreachable(FhirErrorCategory.VALIDATION_ERROR, null);
        }
        try {
            int status = probe.get(metadata, timeout);
            if (status >= 200 && status < 400) {
                return FhirConnectivityStatus.reachable(status);
            }
            return FhirConnectivityStatus.unreachable(FhirErrorClassifier.categoryForStatus(status), status);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            return FhirConnectivityStatus.unreachable(FhirErrorCategory.TIMEOUT, null);
        } catch (Exception ex) {
            FhirErrorDetails details = FhirErrorClassifier.classify(ex);
            return FhirConnectivityStatus.unreachable(details.category(), details.status());
        }
    }

    static URI metadataUri(String fhirBaseUrl) {
        if (fhirBaseUrl == null || fhirBaseUrl.isBlank()) {
            throw new IllegalArgumentException("FHIR base URL must be provided");
        }
        String trimmed = fhirBaseUrl.trim();
        if (trimmed.endsWith("/")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        URI base = URI.create(trimmed);
        String scheme = base.getScheme();
        if (scheme == null
                || !(scheme.equalsIgnoreCase("http") || scheme.equalsIgnoreCase("https"))
                || base.getHost() == null
                || base.getHost().isBlank()) {
            throw new IllegalArgumentException("FHIR base URL must be an http(s) URI with a host");
        }
        if (base.getUserInfo() != null) {
            throw new IllegalArgumentException("FHIR base URL must not contain credentials");
        }
        return URI.create(trimmed + "/metadata");
    }

    private static Probe defaultProbe() {
        HttpClient client = HttpClient.newBuilder().connectTimeout(DEFAULT_TIMEOUT).build();
        return (uri, timeout) -> {
            HttpRequest request = HttpRequest.newBuilder(uri)
                    .timeout(timeout)
                    .header("Accept", "application/fhir+json")
                    .GET()
                    .build();
            HttpResponse<Void> response = client.send(request, HttpResponse.BodyHandlers.discarding());
            return response.statusCode();
        };
    }

    @FunctionalInterface
    interface Probe {
        int get(URI uri, Duration timeout) throws IOException, InterruptedException;
    }
}
