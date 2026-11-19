package lab.healthcare.minihis;

import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

@Component
public class ShowcaseProbe {

    private final HttpClient http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofMillis(400))
            .followRedirects(HttpClient.Redirect.NEVER)
            .build();

    public boolean up(String url) {
        if (!allowed(url)) {
            return false;
        }
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofMillis(700))
                    .header("Accept", "application/json")
                    .GET()
                    .build();
            int status = http.send(request, HttpResponse.BodyHandlers.discarding()).statusCode();
            return status >= 200 && status < 300;
        } catch (Exception ex) {
            return false;
        }
    }

    static boolean allowed(String url) {
        if (url == null || url.isBlank()) {
            return false;
        }
        try {
            URI uri = URI.create(url.trim());
            String scheme = uri.getScheme();
            if (!"http".equalsIgnoreCase(scheme) && !"https".equalsIgnoreCase(scheme)) {
                return false;
            }
            if (uri.getUserInfo() != null || uri.getPort() <= 0 || uri.getHost() == null) {
                return false;
            }
            return LoopbackGuard.isLoopback(uri.getHost());
        } catch (Exception ex) {
            return false;
        }
    }
}
