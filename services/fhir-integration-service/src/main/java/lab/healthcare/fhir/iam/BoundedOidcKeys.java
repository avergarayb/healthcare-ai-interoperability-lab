package lab.healthcare.fhir.iam;

import com.fasterxml.jackson.databind.JsonNode;
import com.nimbusds.jose.jwk.RSAKey;
import java.net.Proxy;
import java.net.ProxySelector;
import java.net.SocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.ByteBuffer;
import java.security.Key;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionStage;
import java.util.concurrent.Flow;
import java.util.concurrent.TimeUnit;
import java.util.function.Function;
import java.util.function.LongSupplier;

/** Per-registration coalesced bounded cache. Nimbus owns public-key conversion/verification. */
final class BoundedOidcKeys {
    private final JavaOidcTrust trust;
    private final Function<String, JsonNode> fetch;
    private final LongSupplier clock;
    private Map<String, Key> keys = Map.of();
    private Long loaded, attempted;

    BoundedOidcKeys(JavaOidcTrust trust) {
        this(trust, new Metadata(trust)::get, () -> System.nanoTime() / 1_000_000_000L);
    }
    BoundedOidcKeys(JavaOidcTrust trust, Function<String, JsonNode> fetch, LongSupplier clock) {
        this.trust = trust; this.fetch = fetch; this.clock = clock;
    }
    synchronized List<Key> select(String kid) {
        long now = clock.getAsLong();
        boolean hard = loaded == null || now - loaded >= trust.jwksHardTtlSeconds();
        if ((hard || !keys.containsKey(kid) || now - loaded >= trust.jwksRefreshSeconds())
                && (attempted == null || now - attempted >= trust.unknownKidRefreshMinIntervalSeconds())) {
            attempted = now;
            try { refresh(); }
            catch (JavaOidcFailure failure) {
                if (!failure.reason.equals("provider_unavailable")) { loaded = null; keys = Map.of(); }
                if (hard || !keys.containsKey(kid) || !failure.reason.equals("provider_unavailable")) { throw failure; }
            }
        }
        if (loaded == null || clock.getAsLong() - loaded >= trust.jwksHardTtlSeconds()) {
            throw new JavaOidcFailure("keys_unavailable", 503);
        }
        Key key = keys.get(kid);
        if (key == null) { throw new JavaOidcFailure("unknown_key", 401); }
        return List.of(key);
    }
    private void refresh() {
        JsonNode discovery = fetch.apply(trust.discoveryUrl());
        if (!trust.issuer().equals(discovery.path("issuer").asText())
                || !trust.expectedJwksUri().equals(discovery.path("jwks_uri").asText())
                || !trust.endpointAllowlist().contains(discovery.path("token_endpoint").asText())
                || !trust.endpointAllowlist().contains(discovery.path("authorization_endpoint").asText())) {
            throw new JavaOidcFailure("discovery_mismatch", 503);
        }
        JsonNode array = fetch.apply(trust.expectedJwksUri()).path("keys");
        if (!array.isArray() || array.isEmpty() || array.size() > 32) { throw new JavaOidcFailure("keys_invalid", 503); }
        Map<String, Key> replacement = new HashMap<>();
        for (JsonNode value : array) {
            for (String field : List.of("d", "p", "q", "dp", "dq", "qi", "oth")) {
                if (value.has(field)) { throw new JavaOidcFailure("keys_invalid", 503); }
            }
            if (!value.isObject()) { throw new JavaOidcFailure("keys_invalid", 503); }
            if (!"RSA".equals(value.path("kty").asText()) || !"sig".equals(value.path("use").asText())
                    || !"RS256".equals(value.path("alg").asText())) { continue; }
            String kid = value.path("kid").asText();
            try {
                if (!value.path("kid").isTextual() || !kid.matches("[A-Za-z0-9_.-]{1,128}") || replacement.containsKey(kid)
                        || !value.path("n").isTextual() || value.path("n").asText().length() > 1400
                        || !value.path("e").isTextual() || value.path("e").asText().length() > 16
                        || (value.has("key_ops") && !value.get("key_ops").equals(JavaOidcTrust.JSON.readTree("[\"verify\"]")))) {
                    throw new IllegalArgumentException();
                }
                RSAKey rsa = RSAKey.parse(value.toString());
                var key = rsa.toRSAPublicKey();
                if (rsa.isPrivate() || key.getModulus().bitLength() < 2048 || key.getModulus().bitLength() > 8192) {
                    throw new IllegalArgumentException();
                }
                replacement.put(kid, key);
            } catch (Exception invalid) { throw new JavaOidcFailure("keys_invalid", 503); }
        }
        if (replacement.isEmpty()) { throw new JavaOidcFailure("keys_invalid", 503); }
        keys = Map.copyOf(replacement); loaded = clock.getAsLong();
    }

    static final class Metadata {
        private final JavaOidcTrust trust;
        private final HttpClient client;
        Metadata(JavaOidcTrust trust) {
            this.trust = trust;
            client = HttpClient.newBuilder().followRedirects(HttpClient.Redirect.NEVER)
                    .connectTimeout(Duration.ofMillis(trust.httpTimeoutMillis()))
                    .proxy(new ProxySelector() {
                        public List<Proxy> select(URI uri) { return List.of(Proxy.NO_PROXY); }
                        public void connectFailed(URI uri, SocketAddress address, java.io.IOException failure) { }
                    }).build();
        }
        JsonNode get(String url) {
            if (!List.of(trust.discoveryUrl(), trust.expectedJwksUri()).contains(url)) {
                throw new JavaOidcFailure("discovery_mismatch", 503);
            }
            var request = HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofMillis(trust.httpTimeoutMillis()))
                    .header("Accept", "application/json").header("Accept-Encoding", "identity").GET().build();
            CompletableFuture<HttpResponse<byte[]>> future = client.sendAsync(request, info -> new LimitedBody(trust.metadataMaxBytes()));
            try {
                var response = future.get(trust.httpTimeoutMillis(), TimeUnit.MILLISECONDS);
                if (response.statusCode() != 200 || !response.headers().firstValue("content-encoding").orElse("identity").equalsIgnoreCase("identity")) {
                    throw new JavaOidcFailure("provider_unavailable", 503);
                }
                JsonNode json = JavaOidcTrust.JSON.readTree(response.body());
                if (json == null || !json.isObject()) { throw new JavaOidcFailure("discovery_mismatch", 503); }
                return json;
            } catch (JavaOidcFailure failure) { throw failure; }
            catch (com.fasterxml.jackson.core.JsonProcessingException invalid) {
                throw new JavaOidcFailure("discovery_mismatch", 503);
            }
            catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt(); throw new JavaOidcFailure("provider_unavailable", 503);
            } catch (Exception failure) { throw new JavaOidcFailure("provider_unavailable", 503); }
            finally { if (!future.isDone()) { future.cancel(true); } }
        }
    }
    private static final class LimitedBody implements HttpResponse.BodySubscriber<byte[]> {
        private final int max;
        private final java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
        private final CompletableFuture<byte[]> body = new CompletableFuture<>();
        private Flow.Subscription subscription;
        LimitedBody(int max) { this.max = max; }
        public CompletionStage<byte[]> getBody() { return body; }
        public void onSubscribe(Flow.Subscription s) { subscription = s; s.request(1); }
        public void onNext(List<ByteBuffer> buffers) {
            for (ByteBuffer buffer : buffers) {
                if (buffer.remaining() > max - bytes.size()) {
                    subscription.cancel(); body.completeExceptionally(new IllegalStateException("metadata_limit")); return;
                }
                byte[] piece = new byte[buffer.remaining()]; buffer.get(piece); bytes.writeBytes(piece);
            }
            subscription.request(1);
        }
        public void onError(Throwable error) { body.completeExceptionally(error); }
        public void onComplete() { body.complete(bytes.toByteArray()); }
    }
}
