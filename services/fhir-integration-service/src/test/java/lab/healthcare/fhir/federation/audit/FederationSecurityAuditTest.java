package lab.healthcare.fhir.federation.audit;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FederationSecurityAuditTest {

    @TempDir
    Path temp;

    @Test
    void sqliteStorePersistsAllowedAndDeniedDecisionsAcrossInstances() {
        Path database = temp.resolve("security-audit.sqlite");
        SqliteFederationSecurityAuditRecorder first = new SqliteFederationSecurityAuditRecorder(database);
        FederationSecurityAudit audit = audit(first);

        audit.allowed("mini-his", "org-mini-his", "FED-0123456789ABCDEF");
        audit.authenticationDenied("participant_token_missing");

        List<FederationSecurityAuditEvent> stored =
                new SqliteFederationSecurityAuditRecorder(database).recorded();
        assertThat(stored).hasSize(2);
        assertThat(stored).extracting(FederationSecurityAuditEvent::outcome)
                .containsExactly("allowed", "denied");
        assertThat(stored.getFirst().timestampUtc())
                .isEqualTo(Instant.parse("2026-10-23T12:00:00Z"));
        assertThat(stored.getFirst().contractVersion()).isEqualTo("security-audit-v1");
    }

    @Test
    void concurrentRecordersUseWalAndPreserveEveryAppend() throws Exception {
        Path database = temp.resolve("concurrent").resolve("security-audit.sqlite");
        List<SqliteFederationSecurityAuditRecorder> stores = List.of(
                new SqliteFederationSecurityAuditRecorder(database),
                new SqliteFederationSecurityAuditRecorder(database),
                new SqliteFederationSecurityAuditRecorder(database),
                new SqliteFederationSecurityAuditRecorder(database));
        CountDownLatch ready = new CountDownLatch(stores.size());
        CountDownLatch start = new CountDownLatch(1);
        ExecutorService executor = Executors.newFixedThreadPool(stores.size());
        List<Future<?>> writes = new ArrayList<>();
        try {
            for (SqliteFederationSecurityAuditRecorder store : stores) {
                writes.add(executor.submit(() -> {
                    ready.countDown();
                    start.await();
                    FederationSecurityAudit audit = audit(store);
                    for (int event = 0; event < 10; event++) {
                        audit.allowed("mini-his", "org-mini-his", "FED-0123456789ABCDEF");
                    }
                    return null;
                }));
            }
            assertThat(ready.await(5, TimeUnit.SECONDS)).isTrue();
            start.countDown();
            for (Future<?> write : writes) {
                write.get(20, TimeUnit.SECONDS);
            }
        } finally {
            start.countDown();
            executor.shutdownNow();
            assertThat(executor.awaitTermination(5, TimeUnit.SECONDS)).isTrue();
        }

        assertThat(stores.getFirst().recorded()).hasSize(40);
        try (Connection connection = DriverManager.getConnection("jdbc:sqlite:" + database.toAbsolutePath());
                Statement statement = connection.createStatement();
                ResultSet mode = statement.executeQuery("PRAGMA journal_mode")) {
            assertThat(mode.next()).isTrue();
            assertThat(mode.getString(1)).isEqualToIgnoringCase("wal");
        }
    }

    @Test
    void distinctStorePathsDoNotMixServiceInstances() {
        SqliteFederationSecurityAuditRecorder first =
                new SqliteFederationSecurityAuditRecorder(temp.resolve("instance-a").resolve("audit.sqlite"));
        SqliteFederationSecurityAuditRecorder second =
                new SqliteFederationSecurityAuditRecorder(temp.resolve("instance-b").resolve("audit.sqlite"));

        audit(first).allowed("mini-his", "org-mini-his", "FED-0123456789ABCDEF");
        audit(second).allowed("mini-lis", "org-mini-lis", "FED-ABCDEF0123456789");

        assertThat(first.recorded()).extracting(FederationSecurityAuditEvent::actorId)
                .containsExactly("mini-his");
        assertThat(second.recorded()).extracting(FederationSecurityAuditEvent::actorId)
                .containsExactly("mini-lis");
    }

    @Test
    void initializationCreatesParentsAndRejectsAnInvalidStoragePath() throws IOException {
        Path nested = temp.resolve("nested").resolve("audit").resolve("security-audit.sqlite");
        new SqliteFederationSecurityAuditRecorder(nested);
        assertThat(nested).exists().isRegularFile();

        Path regularFile = temp.resolve("not-a-directory");
        Files.writeString(regularFile, "synthetic blocking file");
        assertThatThrownBy(() -> new SqliteFederationSecurityAuditRecorder(
                        regularFile.resolve("security-audit.sqlite")))
                .isInstanceOf(FederationSecurityAuditUnavailable.class)
                .hasCauseInstanceOf(IOException.class);
    }

    @Test
    void contractRejectsCrossEventMetadataAndUnverifiedOrganizations() {
        List<FederationSecurityAuditEvent> events = new ArrayList<>();
        FederationSecurityAudit audit = audit(events::add);
        FederationSecurityAuditEvent valid = audit.allowed(
                "mini-his", "Org.Peru-1", "FED-0123456789ABCDEF");

        assertThatThrownBy(() -> copy(valid, Map.of(
                        "route", FederationSecurityAuditEvent.ROUTE,
                        "patient", "MHS-PAT-001"),
                valid.organizationId()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("metadata is invalid");
        assertThatThrownBy(() -> copy(valid, valid.metadata(), null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("organization_id is invalid");
    }

    @Test
    void untrustedCorrelationIsReplacedAndDatabaseFilesContainNoClinicalOrSecretMaterial()
            throws IOException {
        Path database = temp.resolve("security-audit.sqlite");
        SqliteFederationSecurityAuditRecorder store = new SqliteFederationSecurityAuditRecorder(database);
        FederationSecurityAuditEvent event = audit(store).allowed(
                "mini-his", "org-mini-his", "MHS-PAT-001");

        assertThat(event.correlationId())
                .matches("FED-[A-F0-9]{16}")
                .isNotEqualTo("MHS-PAT-001");
        byte[] bytes;
        try (var paths = Files.list(temp)) {
            bytes = paths
                    .filter(path -> path.getFileName().toString().startsWith("security-audit.sqlite"))
                    .map(FederationSecurityAuditTest::read)
                    .reduce(new byte[0], FederationSecurityAuditTest::join);
        }
        String raw = new String(bytes, java.nio.charset.StandardCharsets.ISO_8859_1);
        assertThat(raw)
                .doesNotContain("MHS-PAT-001")
                .doesNotContain("synthetic-participant-token")
                .doesNotContain("Patient/")
                .doesNotContain("Observation")
                .doesNotContain("141")
                .doesNotContain("Quispe");
    }

    private static FederationSecurityAudit audit(FederationSecurityAuditRecorder recorder) {
        return new FederationSecurityAudit(
                recorder,
                Clock.fixed(Instant.parse("2026-10-23T12:00:00Z"), ZoneOffset.UTC));
    }

    private static FederationSecurityAuditEvent copy(
            FederationSecurityAuditEvent event,
            Map<String, String> metadata,
            String organizationId) {
        return new FederationSecurityAuditEvent(
                event.eventId(),
                event.timestampUtc(),
                event.eventType(),
                event.sourceService(),
                event.actorType(),
                event.actorId(),
                organizationId,
                event.action(),
                event.resourceType(),
                event.resourceReference(),
                event.outcome(),
                event.reasonCode(),
                event.correlationId(),
                metadata,
                event.contractVersion());
    }

    private static byte[] read(Path path) {
        try {
            return Files.readAllBytes(path);
        } catch (IOException ex) {
            throw new IllegalStateException(ex);
        }
    }

    private static byte[] join(byte[] left, byte[] right) {
        byte[] joined = new byte[left.length + right.length];
        System.arraycopy(left, 0, joined, 0, left.length);
        System.arraycopy(right, 0, joined, left.length, right.length);
        return joined;
    }
}
