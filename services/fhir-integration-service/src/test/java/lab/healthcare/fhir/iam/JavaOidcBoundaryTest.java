package lab.healthcare.fhir.iam;

import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.DriverManager;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static lab.healthcare.fhir.iam.JavaOidcTestSupport.*;
import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class JavaOidcBoundaryTest {
    @TempDir Path temp;
    @Test void validWorkloadHasMinimalContextAndPersistentAudit() throws Exception {
        Path path = temp.resolve("audit.sqlite");
        var mvc = mvc(boundary(trust(), path));
        String encoded = token(Map.of());
        mvc.perform(get(JavaOidcTrust.ROUTE).header("Authorization", "Bearer " + encoded))
            .andExpect(status().isOk()).andExpect(header().string("Cache-Control", "no-store"))
            .andExpect(jsonPath("$.internal_principal_id").value("fixture-python-to-java"))
            .andExpect(jsonPath("$.organization_id").value("org-lab-b"))
            .andExpect(jsonPath("$.effective_permissions[0]").value(JavaOidcTrust.PERMISSION))
            .andExpect(jsonPath("$.external_subject").doesNotExist()).andExpect(jsonPath("$.external_issuer").doesNotExist())
            .andExpect(jsonPath("$.provider_id").doesNotExist());
        assertAudit(path, "access_granted", "allowed", 1);
        // Reopen using another sink: no in-memory-only evidence.
        new JavaOidcAudit(path.toString(), List.of()).append("credential_missing", java.util.UUID.randomUUID().toString(), null, null);
        assertAudit(path, "credential_missing", "denied", 1);
    }
    @ParameterizedTest @ValueSource(strings={"signature","algorithm","kid","issuer","audience","ai-audience","expired","nbf","iat","long-life","id-token","unknown-client","human-subject","jku","duplicate-claims","missing-exp","boolean-time","excess-audiences"})
    void invalidTokensDenyWithoutContext(String fault) throws Exception {
        Path audit = temp.resolve("audit.sqlite");
        long now = Instant.now().getEpochSecond();
        Map<String,Object> changes = switch(fault) {
            case "issuer" -> Map.of("iss", "https://untrusted.example.invalid");
            case "audience", "ai-audience" -> Map.of("aud", "healthcare-ai-api");
            case "expired" -> Map.of("exp", now - 1);
            case "nbf" -> Map.of("nbf", now + 60);
            case "iat" -> Map.of("iat", now + 60);
            case "long-life" -> Map.of("exp", now + 600);
            case "id-token" -> Map.of("typ", "ID");
            case "unknown-client" -> Map.of("azp", "unknown");
            case "human-subject" -> Map.of("sub", "human-subject");
            default -> Map.of();
        };
        String encoded = token(changes, fault.equals("signature") ? SECOND : KEY, fault.equals("kid") ? "missing" : "known");
        if (List.of("algorithm", "jku", "duplicate-claims", "missing-exp", "boolean-time", "excess-audiences").contains(fault)) {
            String[] parts = encoded.split("\\.");
            var header = (ObjectNode)JavaOidcTrust.JSON.readTree(java.util.Base64.getUrlDecoder().decode(parts[0]));
            var payload = (ObjectNode)JavaOidcTrust.JSON.readTree(java.util.Base64.getUrlDecoder().decode(parts[1]));
            if (fault.equals("algorithm")) { header.put("alg", "HS256"); }
            if (fault.equals("jku")) { header.put("jku", "http://169.254.169.254/"); }
            if (fault.equals("missing-exp")) { payload.remove("exp"); }
            if (fault.equals("boolean-time")) { payload.put("iat", true); }
            if (fault.equals("excess-audiences")) { payload.putArray("aud").add(JavaOidcTrust.AUDIENCE).add("healthcare-ai-api"); }
            String raw = payload.toString();
            if (fault.equals("duplicate-claims")) { raw = raw.replaceFirst("\\{", "{\"iss\":\"duplicate\","); }
            encoded = signedJson(raw, header);
        }
        mvc(boundary(trust(), audit)).perform(get(JavaOidcTrust.ROUTE).header("Authorization", "Bearer " + encoded))
            .andExpect(status().isUnauthorized()).andExpect(content().json("{\"error\":\"unauthorized\"}"))
            .andExpect(header().string("WWW-Authenticate", "Bearer"));
        try(var connection = DriverManager.getConnection("jdbc:sqlite:" + audit); var statement = connection.createStatement();
                var rows = statement.executeQuery("SELECT actor_type,actor_id,organization_id FROM java_oidc_security_audit_v1")) {
            assertThat(rows.next()).isTrue(); assertThat(rows.getString(1)).isEqualTo("anonymous");
            assertThat(rows.getString(2)).isNull(); assertThat(rows.getString(3)).isNull();
        }
    }
    @ParameterizedTest @ValueSource(strings={"absent","duplicate","combined","lowercase","padding","oversize","legacy","cookie"})
    void credentialsMustBeSingleAndUnambiguous(String fault) throws Exception {
        var request = get(JavaOidcTrust.ROUTE);
        String encoded = token(Map.of());
        switch(fault) {
            case "duplicate" -> request.header("Authorization", "Bearer " + encoded, "Bearer " + encoded);
            case "combined" -> request.header("Authorization", "Bearer " + encoded + ", Bearer " + encoded);
            case "lowercase" -> request.header("Authorization", "bearer " + encoded);
            case "padding" -> request.header("Authorization", "Bearer  " + encoded);
            case "oversize" -> request.header("Authorization", "Bearer " + "a".repeat(17000));
            case "legacy" -> request.header("Authorization", "Bearer " + encoded).header("X-Service-Token", "synthetic-invalid");
            case "cookie" -> request.header("Authorization", "Bearer " + encoded).header("Cookie", "lab=synthetic");
            default -> { }
        }
        mvc(boundary(trust(), temp.resolve("audit.sqlite"))).perform(request).andExpect(status().isUnauthorized());
    }
    @ParameterizedTest @ValueSource(strings={"binding","principal","permission","membership","organization","cross-org","ambiguous-org"})
    void trustedLocalPolicyCannotBeExpandedByClaims(String fault) throws Exception {
        var data = registration();
        var binding = (ObjectNode)data.path("bindings").get(0);
        if (fault.equals("binding")) { binding.put("binding_enabled", false); }
        if (fault.equals("principal")) { binding.put("principal_enabled", false); }
        if (fault.equals("permission")) { binding.putArray("permissions").add("iam.workload-context.read"); }
        if (fault.equals("membership")) { binding.put("membership_enabled", false); }
        if (fault.equals("organization")) { binding.put("organization_id", "not-allowed"); }
        String encoded = token(Map.of("roles", List.of(JavaOidcTrust.PERMISSION), "groups", List.of("admin"), "organization", "org-lab-a"));
        var req = get(JavaOidcTrust.ROUTE).header("Authorization", "Bearer " + encoded);
        if (fault.equals("cross-org")) { req.header("X-IAM-Lab-Organization", "org-lab-a"); }
        if (fault.equals("ambiguous-org")) { req.header("X-IAM-Lab-Organization", "org-lab-b", "org-lab-b"); }
        mvc(boundary(trust(data), temp.resolve("audit.sqlite"))).perform(req)
            .andExpect(status().is(fault.equals("binding") || fault.equals("principal") ? 401 : 403));
    }
    @Test void mandatoryAuditWriteLockSuppressesContext() throws Exception {
        Path path = temp.resolve("audit.sqlite");
        var mvc = mvc(boundary(trust(), path));
        String encoded = token(Map.of());
        mvc.perform(get(JavaOidcTrust.ROUTE).header("Authorization", "Bearer " + encoded)).andExpect(status().isOk());
        try(var connection = DriverManager.getConnection("jdbc:sqlite:" + path); var statement=connection.createStatement()) {
            statement.execute("BEGIN IMMEDIATE");
            mvc.perform(get(JavaOidcTrust.ROUTE).header("Authorization", "Bearer " + encoded))
                .andExpect(status().isServiceUnavailable()).andExpect(content().json("{\"error\":\"unavailable\"}"));
            statement.execute("ROLLBACK");
        }
        assertAudit(path, "access_granted", "allowed", 1);
    }
    @Test void foreignAuditSchemaIsNotAdopted() throws Exception {
        Path path = temp.resolve("foreign.sqlite");
        try(var connection = DriverManager.getConnection("jdbc:sqlite:" + path); var statement=connection.createStatement()) {
            statement.execute("CREATE TABLE foreign_store(value TEXT)");
        }
        byte[] before = Files.readAllBytes(path);
        mvc(boundary(trust(), path)).perform(get(JavaOidcTrust.ROUTE).header("Authorization", "Bearer " + token(Map.of())))
            .andExpect(status().isServiceUnavailable());
        assertThat(Files.readAllBytes(path)).isEqualTo(before);
    }
    @Test void invalidTrustIs503AndNeverFallsBack() throws Exception {
        var boundary = new JavaOidcBoundary(temp.resolve("absent.json").toString(), temp.resolve("audit.sqlite").toString(), List.of());
        mvc(boundary).perform(get(JavaOidcTrust.ROUTE).header("Authorization", "Bearer " + token(Map.of())))
            .andExpect(status().isServiceUnavailable()).andExpect(content().json("{\"error\":\"unavailable\"}"));
        assertAudit(temp.resolve("audit.sqlite"), "configuration_incomplete", "denied", 1);
    }
    @Test void contextAndProviderAreNeverLoggedThroughToString() throws Exception {
        var context = new JavaPrincipalContext("fixture-java", "org-lab-b", "provider", "issuer", SUBJECT,
                Instant.now(), Instant.now().plusSeconds(30), java.util.UUID.randomUUID().toString());
        assertThat(context.toString()).doesNotContain(SUBJECT, "issuer");
        assertThat(trust().toString()).doesNotContain(SUBJECT);
        assertThat(context.projection()).doesNotContainKeys("external_subject", "external_issuer", "provider_id");
    }
    @Test void unavailableProviderIsAudited503ThroughSpringProvider() throws Exception {
        var trust=trust(); Path path=temp.resolve("audit.sqlite");
        var keys=new BoundedOidcKeys(trust,url -> { throw new JavaOidcFailure("provider_unavailable",503); },()->0L);
        var verifier=new JavaWorkloadVerifier(trust,keys,java.time.Clock.systemUTC());
        mvc(new JavaOidcBoundary(trust,verifier,new JavaOidcAudit(path.toString(),List.of()),java.time.Clock.systemUTC()))
            .perform(get(JavaOidcTrust.ROUTE).header("Authorization","Bearer "+token(Map.of())))
            .andExpect(status().isServiceUnavailable()).andExpect(content().json("{\"error\":\"unavailable\"}"));
        assertAudit(path,"provider_unavailable","denied",1);
    }
    @Test void disabledProviderNeverUsesKeysOrLegacyFallback() throws Exception {
        var data=registration(); data.put("enabled",false); Path path=temp.resolve("audit.sqlite");
        mvc(boundary(trust(data),path)).perform(get(JavaOidcTrust.ROUTE).header("Authorization","Bearer "+token(Map.of())))
            .andExpect(status().isServiceUnavailable());
        assertAudit(path,"provider_disabled","denied",1);
    }
    @Test void tokenExpiringDuringAuditSuppressesProjectionWithoutInventingAnotherEvent() throws Exception {
        var trust=trust(); Path path=temp.resolve("audit.sqlite"); Instant base=Instant.now();
        var calls=new java.util.concurrent.atomic.AtomicInteger();
        var clock=new java.time.Clock() {
            public java.time.ZoneId getZone() { return java.time.ZoneOffset.UTC; }
            public java.time.Clock withZone(java.time.ZoneId zone) { return this; }
            public Instant instant() { return calls.incrementAndGet()>=3 ? base.plusSeconds(500) : base; }
        };
        var verifier=new JavaWorkloadVerifier(trust,new BoundedOidcKeys(trust,fetcher(trust,KEY),()->0L),java.time.Clock.fixed(base,java.time.ZoneOffset.UTC));
        mvc(new JavaOidcBoundary(trust,verifier,new JavaOidcAudit(path.toString(),List.of()),clock))
            .perform(get(JavaOidcTrust.ROUTE).header("Authorization","Bearer "+token(Map.of())))
            .andExpect(status().isUnauthorized()).andExpect(content().json("{\"error\":\"unauthorized\"}"));
        assertAudit(path,"access_granted","allowed",1);
    }
    @Test void sameInternalPrincipalCannotUnionPermissionsFromAnotherCredentialOrganization() throws Exception {
        var data=registration(); data.putArray("allowed_organization_ids").add("org-lab-a").add("org-lab-b");
        var a=(ObjectNode)data.path("bindings").get(0);
        var b=a.deepCopy(); b.put("client_id","other-client").put("external_subject","other-subject");
        a.put("organization_id","org-lab-a").putArray("permissions");
        ((com.fasterxml.jackson.databind.node.ArrayNode)data.get("bindings")).add(b);
        mvc(boundary(trust(data),temp.resolve("audit.sqlite")))
            .perform(get(JavaOidcTrust.ROUTE).header("Authorization","Bearer "+token(Map.of("roles",List.of(JavaOidcTrust.PERMISSION)))))
            .andExpect(status().isForbidden());
    }
    @Test void boundedRegistrationRejectsDuplicateJsonAndOversizeFile() throws Exception {
        Path path=temp.resolve("trust.json");
        Files.writeString(path,registration().toString().replaceFirst("\\{","{\"enabled\":true,"));
        assertThatThrownBy(()->JavaOidcTrust.load(path.toString())).isInstanceOf(JavaOidcFailure.class);
        Files.writeString(path," ".repeat(65537));
        assertThatThrownBy(()->JavaOidcTrust.load(path.toString())).isInstanceOf(JavaOidcFailure.class);
    }
    @Test void concurrentFirstAuditWritesAreSerializedWithoutLostEvents() throws Exception {
        Path path=temp.resolve("audit.sqlite"); var sink=new JavaOidcAudit(path.toString(),List.of());
        try(var pool=java.util.concurrent.Executors.newFixedThreadPool(8)) {
            var tasks=new java.util.ArrayList<java.util.concurrent.Callable<Boolean>>();
            for(int i=0;i<16;i++) { tasks.add(()-> { sink.append("credential_missing",java.util.UUID.randomUUID().toString(),null,null); return true; }); }
            for(var result:pool.invokeAll(tasks)) { assertThat(result.get()).isTrue(); }
        }
        assertAudit(path,"credential_missing","denied",16);
    }
    @ParameterizedTest @ValueSource(strings={"iat-exp","nbf","exp"})
    void numericDatesCannotOverflowIntoTheCurrentTime(String field) throws Exception {
        mvc(boundary(trust(),temp.resolve("audit.sqlite")))
            .perform(get(JavaOidcTrust.ROUTE).header("Authorization","Bearer "+overflowingNumericDates(token(Map.of()),field)))
            .andExpect(status().isUnauthorized()).andExpect(content().json("{\"error\":\"unauthorized\"}"));
    }
    static String overflowingNumericDates(String encoded,String field) throws Exception {
        String[] parts=encoded.split("\\.");
        var header=(ObjectNode)JavaOidcTrust.JSON.readTree(java.util.Base64.getUrlDecoder().decode(parts[0]));
        var payload=(ObjectNode)JavaOidcTrust.JSON.readTree(java.util.Base64.getUrlDecoder().decode(parts[1]));
        // Validly signed raw NumericDates; do not normalize them through JWTClaimsSet before signing.
        long rolloverSeconds=Long.divideUnsigned(-1L,1000L)+1;
        long raw=Instant.now().getEpochSecond()-1+rolloverSeconds;
        if(field.equals("iat-exp")) { payload.put("iat",raw).put("exp",raw+180); }
        else { payload.put(field,field.equals("exp")?raw+180:raw); }
        return signedJson(payload.toString(),header);
    }
    static void assertAudit(Path path, String reason, String outcome, int count) throws Exception {
        try(var connection=DriverManager.getConnection("jdbc:sqlite:" + path); var query=connection.prepareStatement(
                "SELECT count(*) FROM java_oidc_security_audit_v1 WHERE reason_code=? AND outcome=?")) {
            query.setString(1, reason); query.setString(2, outcome);
            try(var rows=query.executeQuery()) { assertThat(rows.next()).isTrue(); assertThat(rows.getInt(1)).isEqualTo(count); }
        }
    }
}
