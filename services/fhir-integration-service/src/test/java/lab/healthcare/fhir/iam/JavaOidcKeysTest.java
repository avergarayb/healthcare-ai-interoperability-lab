package lab.healthcare.fhir.iam;

import com.fasterxml.jackson.databind.node.ObjectNode;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static lab.healthcare.fhir.iam.JavaOidcTestSupport.*;
import static org.assertj.core.api.Assertions.*;

class JavaOidcKeysTest {
    @Test void refreshesAreCoalescedAndUnknownKidsDoNotGrowARequestCache() throws Exception {
        var trust = trust(); var calls = new AtomicInteger(); var time = new AtomicLong();
        var cache = new BoundedOidcKeys(trust, url -> { calls.incrementAndGet(); return fetcher(trust, KEY).apply(url); }, time::get);
        cache.select("known");
        try(var threads = Executors.newFixedThreadPool(8)) {
            var jobs = new ArrayList<java.util.concurrent.Callable<Integer>>();
            for(int i=0; i<32; i++) { final int kid=i; jobs.add(() -> {
                try { cache.select("unknown-" + kid); return 200; } catch(JavaOidcFailure failure) { return failure.status; }
            }); }
            for(var job : threads.invokeAll(jobs)) { assertThat(job.get()).isEqualTo(401); }
        }
        assertThat(calls.get()).isEqualTo(2);
        time.set(30);
        assertThatThrownBy(() -> cache.select("unknown")).isInstanceOf(JavaOidcFailure.class);
        assertThat(calls.get()).isEqualTo(4);
    }
    @Test void successfulRotationRemovesOldKey() throws Exception {
        var trust = trust(); var time = new AtomicLong(); var current = new AtomicReference<>(KEY);
        var cache = new BoundedOidcKeys(trust, url -> fetcher(trust, current.get()).apply(url), time::get);
        cache.select("known"); current.set(SECOND); time.set(30);
        assertThat(cache.select("rotated")).hasSize(1);
        assertThatThrownBy(() -> cache.select("known")).isInstanceOfSatisfying(JavaOidcFailure.class, e -> assertThat(e.status).isEqualTo(401));
    }
    @Test void networkOutageKeepsKnownKeysOnlyWithinHardTtl() throws Exception {
        var trust=trust(); var time=new AtomicLong(); var down=new java.util.concurrent.atomic.AtomicBoolean();
        var cache=new BoundedOidcKeys(trust, url -> {
            if(down.get()) { throw new JavaOidcFailure("provider_unavailable",503); }
            return fetcher(trust,KEY).apply(url);
        }, time::get);
        cache.select("known"); down.set(true); time.set(300);
        assertThat(cache.select("known")).hasSize(1);
        time.set(900);
        assertThatThrownBy(() -> cache.select("known")).isInstanceOfSatisfying(JavaOidcFailure.class,e -> assertThat(e.status).isEqualTo(503));
    }
    @Test void invalidDiscoveryInvalidatesEvenPreviouslyKnownKeys() throws Exception {
        var trust=trust(); var time=new AtomicLong(); var invalid=new java.util.concurrent.atomic.AtomicBoolean();
        var cache=new BoundedOidcKeys(trust,url -> {
            var node=fetcher(trust,KEY).apply(url);
            if(invalid.get() && url.equals(trust.discoveryUrl())) { ((ObjectNode)node).put("issuer","https://untrusted.example.invalid"); }
            return node;
        },time::get);
        cache.select("known"); invalid.set(true); time.set(300);
        assertThatThrownBy(() -> cache.select("known")).isInstanceOf(JavaOidcFailure.class);
        assertThatThrownBy(() -> cache.select("known")).isInstanceOfSatisfying(JavaOidcFailure.class,e -> assertThat(e.reason).isEqualTo("keys_unavailable"));
    }
    @ParameterizedTest @ValueSource(strings={"private","weak","duplicate","bad-ops","oversized","empty","wrong-type","wrong-jwks"})
    void untrustedKeyMaterialFailsClosed(String kind) throws Exception {
        var trust=trust();
        var cache=new BoundedOidcKeys(trust,url -> {
            var node=(ObjectNode)fetcher(trust,KEY).apply(url);
            if(url.equals(trust.discoveryUrl())) {
                if(kind.equals("wrong-jwks")) { node.put("jwks_uri","http://169.254.169.254/"); }
                return node;
            }
            var keys=(com.fasterxml.jackson.databind.node.ArrayNode)node.path("keys");
            var key=(ObjectNode)keys.get(0);
            switch(kind) {
                case "private" -> key.put("d","synthetic-private-param");
                case "weak" -> key.put("n",java.util.Base64.getUrlEncoder().withoutPadding().encodeToString(new byte[128]));
                case "duplicate" -> keys.add(key.deepCopy());
                case "bad-ops" -> key.putArray("key_ops").add("sign");
                case "oversized" -> key.put("n","a".repeat(1500));
                case "empty" -> keys.removeAll();
                case "wrong-type" -> key.put("kty","oct");
                default -> { }
            }
            return node;
        },()->0L);
        assertThatThrownBy(() -> cache.select("known")).isInstanceOfSatisfying(JavaOidcFailure.class,e -> assertThat(e.status).isEqualTo(503));
    }
    @ParameterizedTest @ValueSource(strings={"redirect","oversize","timeout","compressed","malformed","error"})
    void realHttpTransportHasBoundsAndDoesNotFollowRedirects(String fault) throws Exception {
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        var executor=Executors.newCachedThreadPool(); server.setExecutor(executor);
        var redirected=new AtomicInteger(); var observed=new AtomicInteger();
        server.createContext("/unapproved",exchange -> { redirected.incrementAndGet(); exchange.sendResponseHeaders(200,-1); exchange.close(); });
        server.createContext("/discovery",exchange -> {
            observed.incrementAndGet();
            try {
                if(fault.equals("timeout")) { Thread.sleep(500); }
                if(fault.equals("redirect")) { exchange.getResponseHeaders().add("Location","/unapproved"); exchange.sendResponseHeaders(302,-1); }
                else {
                    byte[] body=(fault.equals("oversize") ? "x".repeat(2048) : fault.equals("malformed") ? "not-json" : "{}").getBytes(StandardCharsets.UTF_8);
                    if(fault.equals("compressed")) { exchange.getResponseHeaders().add("Content-Encoding","gzip"); }
                    exchange.sendResponseHeaders(fault.equals("error") ? 500 : 200,body.length); exchange.getResponseBody().write(body);
                }
            } catch(Exception ignored) { } finally { exchange.close(); }
        });
        server.start();
        try {
            var data=registration(); String origin="http://127.0.0.1:"+server.getAddress().getPort();
            data.put("issuer",origin).put("discovery_url",origin+"/discovery").put("expected_jwks_uri",origin+"/keys")
                .put("allow_http_loopback",true).put("http_timeout_millis",fault.equals("timeout") ? 100 : 2000).put("metadata_max_bytes",1024);
            data.putArray("endpoint_allowlist").add(origin+"/discovery").add(origin+"/keys");
            var config=trust(data); var metadata=new BoundedOidcKeys.Metadata(config);
            assertThatThrownBy(() -> metadata.get(config.discoveryUrl())).isInstanceOfSatisfying(JavaOidcFailure.class,e -> assertThat(e.status).isEqualTo(503));
            assertThat(redirected.get()).isZero();
            if(!fault.equals("timeout")) { assertThat(observed.get()).isEqualTo(1); }
            assertThatThrownBy(() -> metadata.get(origin+"/unapproved")).isInstanceOf(JavaOidcFailure.class);
            assertThat(redirected.get()).isZero();
        } finally { server.stop(0); executor.shutdownNow(); }
    }
    @ParameterizedTest @ValueSource(strings={"http-remote","localhost-default","private-ip","wrong-audience","wrong-algorithm","long-ttl","low-throttle","missing","unknown","coerced-boolean","duplicate-binding"})
    void configurationIsClosedAndOperatorOwned(String fault) throws Exception {
        var data=registration();
        switch(fault) {
            case "http-remote" -> data.put("issuer","http://identity.example.invalid");
            case "localhost-default" -> data.put("issuer","https://localhost:18090");
            case "private-ip" -> data.put("issuer","https://169.254.169.254");
            case "wrong-audience" -> data.put("audience","healthcare-ai-api");
            case "wrong-algorithm" -> data.put("algorithm","HS256");
            case "long-ttl" -> data.put("jwks_hard_ttl_seconds",901);
            case "low-throttle" -> data.put("unknown_kid_refresh_min_interval_seconds",1);
            case "missing" -> data.remove("issuer");
            case "unknown" -> data.put("unexpected","value");
            case "coerced-boolean" -> data.put("enabled","true");
            case "duplicate-binding" -> ((com.fasterxml.jackson.databind.node.ArrayNode)data.get("bindings")).add(data.path("bindings").get(0).deepCopy());
        }
        assertThatThrownBy(() -> trust(data)).isInstanceOf(Exception.class);
    }
}
