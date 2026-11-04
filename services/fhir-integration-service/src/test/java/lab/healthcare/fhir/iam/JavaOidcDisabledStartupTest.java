package lab.healthcare.fhir.iam;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Path;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.context.ApplicationContext;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping;
import static org.assertj.core.api.Assertions.*;

// Mini LIS is a test-scope dependency; its JDBC auto-configuration is not part of the Java runtime.
@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT, properties={
    "spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration",
    "logging.level.org.springframework=WARN", "logging.level.root=WARN"})
class JavaOidcDisabledStartupTest {
    static final Path DIRECTORY=Path.of("target","task005-disabled-"+UUID.randomUUID()).toAbsolutePath();
    @DynamicPropertySource static void isolation(DynamicPropertyRegistry properties) {
        properties.add("exchange.store-path",()->DIRECTORY.resolve("exchange.sqlite").toString());
        properties.add("federation.security-audit.store-path",()->DIRECTORY.resolve("federation-audit.sqlite").toString());
        properties.add("MODEL_BOUNDARY_SERVICE_TOKEN",()->"");
        properties.add("IAM_JAVA_WORKLOAD_TRUST_CONFIG_PATH",()->DIRECTORY.resolve("does-not-exist.json").toString());
    }
    @LocalServerPort int port;
    @Autowired ApplicationContext context;
    @Autowired @org.springframework.beans.factory.annotation.Qualifier("requestMappingHandlerMapping") RequestMappingHandlerMapping mappings;
    @Test void defaultStartupNeedsNoProviderAndDoesNotInstallGlobalSecurity() throws Exception {
        assertThat(context.getBeansOfType(SecurityFilterChain.class)).isEmpty();
        assertThat(context.containsBean("springSecurityFilterChain")).isFalse();
        assertThat(context.getBeansOfType(org.springframework.security.core.userdetails.UserDetailsService.class)).isEmpty();
        assertThat(org.springframework.util.ClassUtils.isPresent("org.springframework.security.config.annotation.web.configuration.EnableWebSecurity",getClass().getClassLoader())).isFalse();
        assertThat(mappings.getHandlerMethods().keySet().stream().anyMatch(info->info.toString().contains(JavaOidcTrust.ROUTE))).isFalse();
        var client=HttpClient.newHttpClient();
        assertThat(send(client,"GET","/actuator/health/liveness")).isEqualTo(200);
        assertThat(send(client,"GET",JavaOidcTrust.ROUTE)).isEqualTo(404);
        assertThat(send(client,"GET","/api/model-boundary/v1")).isEqualTo(401);
        assertThat(send(client,"GET","/api/clinical-read/v1/patients/synthetic-not-read")).isEqualTo(401);
        assertThat(send(client,"POST","/api/clinical-federation/v1/context")).isEqualTo(401);
        assertThat(send(client,"POST","/api/exchange/v1/orders")).isEqualTo(401);
        assertThat(DIRECTORY.resolve("does-not-exist.json")).doesNotExist();
    }
    int send(HttpClient client,String method,String path) throws Exception {
        return client.send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:"+port+path))
            .method(method,HttpRequest.BodyPublishers.noBody()).build(),HttpResponse.BodyHandlers.discarding()).statusCode();
    }
}

/** Real Servlet/MVC HTTP, synthetic owned JWKS only; no Keycloak or clinical calls. */
@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT, properties={
    "spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration",
    "logging.level.org.springframework=WARN", "logging.level.root=WARN"})
@org.springframework.test.annotation.DirtiesContext(classMode=org.springframework.test.annotation.DirtiesContext.ClassMode.AFTER_CLASS)
@org.junit.jupiter.api.parallel.Execution(org.junit.jupiter.api.parallel.ExecutionMode.SAME_THREAD)
class JavaOidcHttpMethodsTest {
    static final Path DIRECTORY=Path.of("target","task005-http-review-"+UUID.randomUUID()).toAbsolutePath();
    static final Path AUDIT=DIRECTORY.resolve("iam-audit.sqlite");
    static final java.util.List<java.util.Map<String,Object>> RESULTS=new java.util.ArrayList<>();
    static com.sun.net.httpserver.HttpServer metadata;
    static java.util.concurrent.ExecutorService executor;
    static JavaOidcTrust trust;
    @LocalServerPort int port;
    @Autowired ApplicationContext context;

    @DynamicPropertySource static void isolation(DynamicPropertyRegistry properties) throws Exception {
        java.nio.file.Files.createDirectories(DIRECTORY);
        metadata=com.sun.net.httpserver.HttpServer.create(new java.net.InetSocketAddress("127.0.0.1",0),0);
        executor=java.util.concurrent.Executors.newCachedThreadPool(); metadata.setExecutor(executor);
        String issuer="http://127.0.0.1:"+metadata.getAddress().getPort()+"/realms/synthetic";
        var data=JavaOidcTestSupport.registration();
        data.put("issuer",issuer).put("allow_http_loopback",true)
            .put("discovery_url",issuer+"/.well-known/openid-configuration")
            .put("expected_jwks_uri",issuer+"/protocol/openid-connect/certs");
        var endpoints=data.putArray("endpoint_allowlist");
        for(String suffix:java.util.List.of("/.well-known/openid-configuration","/protocol/openid-connect/certs",
                "/protocol/openid-connect/token","/protocol/openid-connect/auth")) { endpoints.add(issuer+suffix); }
        trust=JavaOidcTestSupport.trust(data);
        var fetch=JavaOidcTestSupport.fetcher(trust,JavaOidcTestSupport.KEY);
        for(String url:java.util.List.of(trust.discoveryUrl(),trust.expectedJwksUri())) {
            metadata.createContext(URI.create(url).getPath(),exchange -> {
                try {
                    byte[] body=JavaOidcTrust.JSON.writeValueAsBytes(fetch.apply(url));
                    exchange.getResponseHeaders().add("Content-Type","application/json");
                    exchange.sendResponseHeaders(200,body.length); exchange.getResponseBody().write(body);
                } finally { exchange.close(); }
            });
        }
        metadata.start();
        Path file=DIRECTORY.resolve("trust.json"); JavaOidcTrust.JSON.writeValue(file.toFile(),data);
        properties.add("iam.java.workload.lab.enabled",()->"true");
        properties.add("IAM_JAVA_WORKLOAD_TRUST_CONFIG_PATH",file::toString);
        properties.add("IAM_JAVA_WORKLOAD_AUDIT_DB_PATH",AUDIT::toString);
        properties.add("exchange.store-path",()->DIRECTORY.resolve("exchange.sqlite").toString());
        properties.add("federation.security-audit.store-path",()->DIRECTORY.resolve("federation-audit.sqlite").toString());
        properties.add("MODEL_BOUNDARY_SERVICE_TOKEN",()->"");
    }
    @org.junit.jupiter.api.AfterAll static void stopFixture() throws Exception {
        try {
            JavaOidcTrust.JSON.writeValue(DIRECTORY.resolve("http-review-results.json").toFile(),java.util.Map.of(
                "category","deterministic_real_servlet_http", "cases",RESULTS, "Keycloak_started",false,
                "clinical_calls","none", "tokens_persisted",false));
        } finally {
            if(metadata!=null) { metadata.stop(0); }
            if(executor!=null) { executor.shutdownNow(); }
        }
    }
    String validToken() throws Exception { return JavaOidcTestSupport.token(java.util.Map.of("iss",trust.issuer())); }
    HttpResponse<byte[]> request(String method,String path,String encoded,String name) throws Exception {
        var builder=HttpRequest.newBuilder(URI.create("http://127.0.0.1:"+port+path))
            .method(method,HttpRequest.BodyPublishers.noBody());
        if(encoded!=null) { builder.header("Authorization","Bearer "+encoded); }
        try(var client=HttpClient.newHttpClient()) {
            var response=client.send(builder.build(),HttpResponse.BodyHandlers.ofByteArray());
            RESULTS.add(java.util.Map.of("case",name,"http_status",response.statusCode(),"body_bytes",response.body().length));
            return response;
        }
    }
    static int rows(String condition) throws Exception {
        if(!java.nio.file.Files.exists(AUDIT)) { return 0; }
        try(var connection=java.sql.DriverManager.getConnection("jdbc:sqlite:"+AUDIT);var query=connection.createStatement();
            var result=query.executeQuery("SELECT count(*) FROM java_oidc_security_audit_v1"+condition)) {
            return result.next()?result.getInt(1):0;
        }
    }
    static void noProjection(HttpResponse<byte[]> response) {
        String body=new String(response.body(),java.nio.charset.StandardCharsets.UTF_8);
        assertThat(body).doesNotContain("internal_principal_id","effective_permissions","external_subject");
    }
    @Test void canonicalGetAuthenticatesAndAuditsExactlyOnce() throws Exception {
        int before=rows("");
        assertThat(request("GET",JavaOidcTrust.ROUTE,null,"GET_missing").statusCode()).isEqualTo(401);
        assertThat(request("GET",JavaOidcTrust.ROUTE,"a.b.c","GET_invalid").statusCode()).isEqualTo(401);
        var response=request("GET",JavaOidcTrust.ROUTE,validToken(),"GET_valid");
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(JavaOidcTrust.JSON.readTree(response.body()).path("internal_principal_id").asText()).isEqualTo("fixture-python-to-java");
        assertThat(rows("")-before).isEqualTo(3);
    }
    @org.junit.jupiter.params.ParameterizedTest @org.junit.jupiter.params.provider.ValueSource(strings={"iat-exp","nbf","exp"})
    void numericDateOverflowIsDeniedThroughRealHttp(String field) throws Exception {
        int before=rows("");
        var response=request("GET",JavaOidcTrust.ROUTE,
            JavaOidcBoundaryTest.overflowingNumericDates(validToken(),field),"NumericDate_"+field);
        assertThat(response.statusCode()).isEqualTo(401); noProjection(response);
        assertThat(rows("")-before).isEqualTo(1);
    }
    @org.junit.jupiter.params.ParameterizedTest @org.junit.jupiter.params.provider.ValueSource(strings={"missing","invalid","valid"})
    void headIsRejectedWithoutProjectionOrAnAuthorizedAudit(String credential) throws Exception {
        int before=rows("");
        String encoded=credential.equals("missing")?null:credential.equals("invalid")?"a.b.c":validToken();
        var response=request("HEAD",JavaOidcTrust.ROUTE,encoded,"HEAD_"+credential);
        assertThat(response.statusCode()).isEqualTo(401); assertThat(response.body()).isEmpty();
        assertThat(response.headers().firstValue("WWW-Authenticate")).contains("Bearer");
        assertThat(response.headers().firstValue("X-Correlation-ID")).isEmpty();
        assertThat(rows("")).isEqualTo(before); // Unsupported HEAD is not an authenticated GET decision.
    }
    @org.junit.jupiter.params.ParameterizedTest @org.junit.jupiter.params.provider.ValueSource(strings={"POST","PUT","PATCH","DELETE"})
    void writeMethodsNeverExecuteProtectedGet(String method) throws Exception {
        int before=rows("");
        for(String encoded:java.util.Arrays.asList(null,validToken())) {
            var response=request(method,JavaOidcTrust.ROUTE,encoded,method+"_"+(encoded==null?"missing":"valid"));
            assertThat(response.statusCode()).isEqualTo(405); noProjection(response);
        }
        assertThat(rows("")).isEqualTo(before);
    }
    @Test void optionsIsOnlyPublicProtocolMetadata() throws Exception {
        int before=rows("");
        for(String encoded:java.util.Arrays.asList(null,validToken())) {
            var response=request("OPTIONS",JavaOidcTrust.ROUTE,encoded,"OPTIONS_"+(encoded==null?"missing":"valid"));
            assertThat(response.statusCode()).isEqualTo(200); assertThat(response.body()).isEmpty(); noProjection(response);
        }
        assertThat(rows("")).isEqualTo(before);
    }
    @org.junit.jupiter.params.ParameterizedTest @org.junit.jupiter.params.provider.ValueSource(strings={
        "/iam-lab/v1/workload-context/", "/iam-lab//v1/workload-context", "/iam-lab/./v1/workload-context",
        "/iam-lab/v1/%77orkload-context", "/iam-lab/v1/workload-context;candidate=synthetic"})
    void pathVariantsCannotBypassTheGuard(String path) throws Exception {
        var anonymous=request("GET",path,null,"variant_missing_"+path);
        assertThat(anonymous.statusCode()).isBetween(400,499); noProjection(anonymous);
        int allowed=rows(" WHERE outcome='allowed'");
        var authenticated=request("GET",path,validToken(),"variant_valid_"+path);
        if(authenticated.statusCode()==200) {
            assertThat(rows(" WHERE outcome='allowed'")-allowed).isEqualTo(1);
            assertThat(JavaOidcTrust.JSON.readTree(authenticated.body()).path("principal_type").asText()).isEqualTo("workload");
        } else { assertThat(authenticated.statusCode()).isBetween(400,499); noProjection(authenticated); }
    }
    @Test void queryParametersCannotSupplyIdentityOrSkipAudit() throws Exception {
        String path=JavaOidcTrust.ROUTE+"?internal_principal_id=admin&organization=org-lab-a";
        assertThat(request("GET",path,null,"query_missing").statusCode()).isEqualTo(401);
        int before=rows(""); var response=request("GET",path,validToken(),"query_valid");
        assertThat(response.statusCode()).isEqualTo(200); assertThat(rows("")-before).isEqualTo(1);
        assertThat(JavaOidcTrust.JSON.readTree(response.body()).path("organization_id").asText()).isEqualTo("org-lab-b");
    }
    @Test void proxyAndBoundaryAreNotRegisteredTwiceOrGlobally() {
        var application=(org.springframework.boot.web.servlet.context.ServletWebServerApplicationContext)context;
        var registrations=application.getServletContext().getFilterRegistrations();
        assertThat(registrations.values().stream().filter(r->r.getClassName().equals(org.springframework.security.web.FilterChainProxy.class.getName())).count()).isEqualTo(1);
        assertThat(registrations.get("javaOidcLabFilter").getUrlPatternMappings()).containsExactly(JavaOidcTrust.ROUTE);
        assertThat(registrations.values().stream().anyMatch(r->r.getClassName().equals(JavaOidcBoundary.class.getName()))).isFalse();
        assertThat(context.getBeansOfType(JavaOidcBoundary.class)).isEmpty();
        assertThat(context.containsBean("springSecurityFilterChain")).isFalse();
        assertThat(context.getBeansOfType(SecurityFilterChain.class)).hasSize(1);
        var registration=(org.springframework.boot.web.servlet.FilterRegistrationBean<?>)context.getBean("javaOidcLabFilter");
        assertThat(registration.getOrder()).isEqualTo(org.springframework.core.Ordered.HIGHEST_PRECEDENCE+10);
        var proxy=(org.springframework.security.web.FilterChainProxy)registration.getFilter();
        assertThat(proxy.getFilterChains()).hasSize(1);
        assertThat(proxy.getFilterChains().getFirst().getFilters()).hasSize(1);
        assertThat(proxy.getFilterChains().getFirst().getFilters().getFirst()).isInstanceOf(JavaOidcBoundary.class);
        var tomcat=(org.springframework.boot.web.embedded.tomcat.TomcatWebServer)application.getWebServer();
        var container=(org.apache.catalina.core.StandardContext)tomcat.getTomcat().getHost().findChildren()[0];
        var mapping=java.util.Arrays.stream(container.findFilterMaps()).filter(m->m.getFilterName().equals("javaOidcLabFilter")).findFirst().orElseThrow();
        assertThat(mapping.getDispatcherNames()).containsExactly("REQUEST");
        RESULTS.add(java.util.Map.of("case","single_filter_registration","dispatchers",java.util.List.of(mapping.getDispatcherNames()),"result","PASS"));
    }
}
