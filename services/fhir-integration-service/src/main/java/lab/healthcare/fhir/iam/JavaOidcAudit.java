package lab.healthcare.fhir.iam;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.time.Instant;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/** Additive workload audit, never a Federation actor/event or a clinical store. */
final class JavaOidcAudit {
    static final Set<String> REASONS = Set.of("access_granted", "credential_missing", "credential_ambiguous",
            "credential_malformed", "credential_conflict", "configuration_incomplete", "provider_disabled",
            "provider_unavailable", "discovery_mismatch", "keys_invalid", "keys_unavailable", "unknown_key",
            "algorithm_rejected", "key_source_rejected", "verification_rejected", "token_expired", "time_rejected",
            "purpose_rejected", "audience_rejected", "issuer_rejected", "binding_unknown", "binding_disabled",
            "principal_disabled", "organization_rejected", "policy_rejected");
    private final Path path;
    JavaOidcAudit(String value, List<String> forbidden) {
        try {
            path = Path.of(value);
            if (!path.isAbsolute() || value.contains("?") || value.contains("#")
                    || value.endsWith("-wal") || value.endsWith("-shm") || value.endsWith("-journal")) { throw new IllegalArgumentException(); }
            for (String other : forbidden) {
                if (other != null && !other.isBlank() && Path.of(other).toAbsolutePath().normalize().equals(path.toAbsolutePath().normalize())) {
                    throw new IllegalArgumentException();
                }
            }
        } catch (Exception invalid) { throw new JavaOidcFailure("audit_unavailable", 503); }
    }
    synchronized void append(String reason, String correlation, String provider, JavaPrincipalContext context) {
        try {
            if (!REASONS.contains(reason) || (context != null) != reason.equals("access_granted")
                    || !UUID.fromString(correlation).toString().equals(correlation)
                    || (provider != null && !JavaOidcTrust.id(provider))) { throw new IllegalArgumentException(); }
            for (Path p = path; p != null; p = p.getParent()) {
                if (Files.isSymbolicLink(p) || (Files.exists(p, LinkOption.NOFOLLOW_LINKS)
                        && Files.readAttributes(p, java.nio.file.attribute.BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS).isOther())) {
                    throw new IllegalArgumentException();
                }
            }
            Files.createDirectories(path.getParent());
            String ddl;
            try (var resource = JavaOidcAudit.class.getResourceAsStream("/iam/001_java_oidc_security_audit.sql")) {
                ddl = new String(resource.readAllBytes(), StandardCharsets.UTF_8).strip();
            }
            try (Connection connection = DriverManager.getConnection("jdbc:sqlite:" + path);
                    var statement = connection.createStatement()) {
                statement.execute("PRAGMA busy_timeout=1000");
                // Inspect before altering journal mode or initializing a preexisting file.
                String existing = null; int objects = 0;
                try (ResultSet rows = statement.executeQuery("SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL")) {
                    while (rows.next()) {
                        objects++;
                        if (!rows.getString(1).equals("java_oidc_security_audit_v1")) { throw new IllegalArgumentException(); }
                        existing = rows.getString(2);
                    }
                }
                int version;
                try (ResultSet rows = statement.executeQuery("PRAGMA user_version")) { version = rows.next() ? rows.getInt(1) : -1; }
                if ((objects == 0 && version != 0) || (objects != 0 && (objects != 1 || version != 1 || !ddl.equals(existing)))) {
                    throw new IllegalArgumentException();
                }
                try (ResultSet rows = statement.executeQuery("PRAGMA journal_mode=WAL")) {
                    if (!rows.next() || !rows.getString(1).equalsIgnoreCase("wal")) { throw new IllegalArgumentException(); }
                }
                statement.execute("BEGIN IMMEDIATE");
                try {
                    if (objects == 0) { statement.execute(ddl); statement.execute("PRAGMA user_version=1"); }
                    try (var insert = connection.prepareStatement("INSERT INTO java_oidc_security_audit_v1 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)")) {
                        String[] fields = {UUID.randomUUID().toString(), Instant.now().toString(), "java-oidc-security-audit-v1",
                                "workload_authentication", "fhir-integration-service", "authenticate_workload", JavaOidcTrust.ROUTE,
                                context == null ? "denied" : "allowed", reason, context == null ? "anonymous" : "workload",
                                context == null ? null : context.internalPrincipalId(), context == null ? null : context.organizationId(),
                                provider, correlation};
                        for (int i = 0; i < fields.length; i++) { insert.setString(i + 1, fields[i]); }
                        insert.executeUpdate();
                    }
                    statement.execute("COMMIT");
                } catch (Exception failure) { statement.execute("ROLLBACK"); throw failure; }
            }
        } catch (Exception unavailable) { throw new JavaOidcFailure("audit_unavailable", 503); }
    }
}
