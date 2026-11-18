package lab.healthcare.minihis;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Pattern;

@Repository
public class InpatientStore {

    private static final Pattern SAFE_TEXT = Pattern.compile("[\\p{L}\\p{N} .,;:()\\-]{1,240}");
    private static final Pattern INJECTION = Pattern.compile(
            "(?i)ignore previous|ignore instructions|system prompt|<script|</");

    private final JdbcTemplate jdbc;

    public InpatientStore(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void ensure() {
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS hospitalization (
                    episode_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
                    version INTEGER NOT NULL,
                    documentation_status TEXT NOT NULL CHECK (documentation_status IN ('none', 'proposed', 'accepted')),
                    opened_at TEXT NOT NULL,
                    opened_by TEXT NOT NULL,
                    closed_at TEXT,
                    closed_by TEXT
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS evolution_note (
                    note_id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS allergy_record (
                    allergy_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    substance TEXT NOT NULL,
                    recorded_by TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS medication_statement (
                    medication_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    documented_status TEXT NOT NULL CHECK (documented_status IN ('active', 'stopped')),
                    recorded_by TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS episode_task (
                    task_id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('open', 'resolved')),
                    kind TEXT NOT NULL CHECK (kind IN ('ward', 'follow_up')),
                    proposal_id TEXT,
                    created_at TEXT NOT NULL
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS episode_result (
                    episode_id TEXT NOT NULL,
                    result_id TEXT NOT NULL,
                    PRIMARY KEY (episode_id, result_id)
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS follow_up_grant (
                    proposal_id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    task_ids TEXT NOT NULL
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS discharge_view (
                    episode_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL,
                    proposal_hash TEXT NOT NULL,
                    episode_version INTEGER NOT NULL,
                    phase TEXT NOT NULL,
                    checklist_complete INTEGER NOT NULL,
                    body_json TEXT NOT NULL
                )
                """);
        jdbc.execute("""
                CREATE TABLE IF NOT EXISTS inpatient_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                )
                """);
    }

    public void clearAll() {
        ensure();
        jdbc.update("DELETE FROM episode_result");
        jdbc.update("DELETE FROM episode_task");
        jdbc.update("DELETE FROM evolution_note");
        jdbc.update("DELETE FROM follow_up_grant");
        jdbc.update("DELETE FROM discharge_view");
        jdbc.update("DELETE FROM inpatient_audit");
        jdbc.update("DELETE FROM allergy_record");
        jdbc.update("DELETE FROM medication_statement");
        jdbc.update("DELETE FROM hospitalization");
    }

    public List<Map<String, Object>> patients() {
        return jdbc.queryForList("""
                SELECT patient_id, family_name, given_name
                FROM patient
                ORDER BY patient_id
                LIMIT 50
                """);
    }

    public Map<String, Object> requirePatient(String patientId) {
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT patient_id, family_name, given_name FROM patient WHERE patient_id = ?",
                patientId);
        if (rows.isEmpty()) {
            throw new InpatientRejection("patient_not_found", 404);
        }
        return rows.get(0);
    }

    @Transactional
    public String openEpisode(String patientId, String organizationId, String actorId) {
        ensure();
        requirePatient(patientId);
        String episodeId = ident("ENC-");
        jdbc.update("""
                INSERT INTO hospitalization (
                    episode_id, patient_id, organization_id, status, version, documentation_status,
                    opened_at, opened_by
                ) VALUES (?, ?, ?, 'open', 1, 'none', ?, ?)
                """, episodeId, patientId, organizationId, now(), actorId);
        audit(episodeId, actorId, "episode_opened", "recorded", episodeId);
        return episodeId;
    }

    public Map<String, Object> episode(String episodeId) {
        ensure();
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT * FROM hospitalization WHERE episode_id = ?", episodeId);
        if (rows.isEmpty()) {
            throw new InpatientRejection("episode_not_found", 404);
        }
        Map<String, Object> episode = new LinkedHashMap<>(rows.get(0));
        episode.put("notes", notes(episodeId));
        episode.put("tasks", tasks(episodeId));
        episode.put("results", linkedResults(episodeId));
        episode.put("allergies", allergies(String.valueOf(episode.get("patient_id"))));
        episode.put("medications", medications(String.valueOf(episode.get("patient_id"))));
        episode.put("availableResults", availableResults(String.valueOf(episode.get("patient_id"))));
        episode.put("checklist", checklist(episode));
        episode.put("audit", auditRows(episodeId));
        episode.put("proposal", proposal(episodeId));
        episode.put("timeline", timeline(episode));
        return episode;
    }

    @Transactional
    public void addNote(String episodeId, int expectedVersion, String actorId, String body) {
        Map<String, Object> current = requireOpen(episodeId, expectedVersion);
        String text = requiredText(body);
        jdbc.update(
                "INSERT INTO evolution_note (note_id, episode_id, author_id, body, created_at) VALUES (?, ?, ?, ?, ?)",
                ident("NOTE-"), episodeId, actorId, text, now());
        bump(episodeId, expectedVersion);
        audit(episodeId, actorId, "note_recorded", "recorded", String.valueOf(current.get("patient_id")));
    }

    @Transactional
    public void addAllergy(String patientId, String actorId, String substance) {
        requirePatient(patientId);
        jdbc.update(
                "INSERT INTO allergy_record (allergy_id, patient_id, substance, recorded_by, recorded_at) VALUES (?, ?, ?, ?, ?)",
                ident("ALG-"), patientId, requiredText(substance), actorId, now());
    }

    @Transactional
    public void addMedication(String patientId, String actorId, String name, String status) {
        requirePatient(patientId);
        if (!"active".equals(status) && !"stopped".equals(status)) {
            throw new InpatientRejection("invalid_input", 400);
        }
        jdbc.update("""
                INSERT INTO medication_statement (
                    medication_id, patient_id, name, documented_status, recorded_by, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """, ident("MED-"), patientId, requiredText(name), status, actorId, now());
    }

    @Transactional
    public void linkResult(String episodeId, int expectedVersion, String actorId, String resultId) {
        Map<String, Object> current = requireOpen(episodeId, expectedVersion);
        Integer owned = jdbc.queryForObject(
                "SELECT COUNT(*) FROM clinical_result WHERE result_id = ? AND patient_id = ?",
                Integer.class, resultId, current.get("patient_id"));
        if (owned == null || owned == 0) {
            throw new InpatientRejection("result_not_found", 404);
        }
        jdbc.update(
                "INSERT OR IGNORE INTO episode_result (episode_id, result_id) VALUES (?, ?)",
                episodeId, resultId);
        bump(episodeId, expectedVersion);
        audit(episodeId, actorId, "result_linked", "recorded", resultId);
    }

    @Transactional
    public void addTask(String episodeId, int expectedVersion, String actorId, String title) {
        requireOpen(episodeId, expectedVersion);
        jdbc.update("""
                INSERT INTO episode_task (task_id, episode_id, title, status, kind, created_at)
                VALUES (?, ?, ?, 'open', 'ward', ?)
                """, ident("TASK-"), episodeId, requiredText(title), now());
        bump(episodeId, expectedVersion);
        audit(episodeId, actorId, "task_opened", "recorded", "ward");
    }

    @Transactional
    public void resolveTask(String episodeId, String taskId, int expectedVersion, String actorId) {
        requireOpen(episodeId, expectedVersion);
        int updated = jdbc.update("""
                UPDATE episode_task SET status = 'resolved'
                WHERE task_id = ? AND episode_id = ? AND kind = 'ward' AND status = 'open'
                """, taskId, episodeId);
        if (updated != 1) {
            throw new InpatientRejection("task_not_open", 409);
        }
        bump(episodeId, expectedVersion);
        audit(episodeId, actorId, "task_resolved", "recorded", taskId);
    }

    @Transactional
    public void rememberProposal(String episodeId, Map<String, Object> proposal) {
        ensure();
        jdbc.update("DELETE FROM discharge_view WHERE episode_id = ?", episodeId);
        jdbc.update("""
                INSERT INTO discharge_view (
                    episode_id, proposal_id, proposal_hash, episode_version, phase, checklist_complete, body_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                episodeId,
                proposal.get("proposalId"),
                proposal.get("proposalHash"),
                proposal.get("episodeVersion"),
                proposal.get("phase"),
                Boolean.TRUE.equals(proposal.get("checklistComplete")) ? 1 : 0,
                String.valueOf(proposal.get("bodyJson")));
        jdbc.update(
                "UPDATE hospitalization SET documentation_status = 'proposed' WHERE episode_id = ? AND status = 'open'",
                episodeId);
    }

    public Map<String, Object> storedProposal(String episodeId) {
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT * FROM discharge_view WHERE episode_id = ?", episodeId);
        return rows.isEmpty() ? Map.of() : rows.get(0);
    }

    @Transactional
    public void markDocumentationAccepted(String episodeId, String actorId, String proposalId) {
        int updated = jdbc.update("""
                UPDATE hospitalization SET documentation_status = 'accepted'
                WHERE episode_id = ? AND status = 'open'
                """, episodeId);
        if (updated != 1) {
            throw new InpatientRejection("episode_not_open", 409);
        }
        audit(episodeId, actorId, "documentation_accepted", "recorded", proposalId);
    }

    @Transactional
    public List<String> createFollowUps(String episodeId, int expectedVersion, String actorId, String proposalId, List<String> titles) {
        requireOpen(episodeId, expectedVersion);
        if (titles == null || titles.isEmpty()) {
            throw new InpatientRejection("nothing_to_create", 409);
        }
        List<String> existing = jdbc.query(
                "SELECT task_ids FROM follow_up_grant WHERE proposal_id = ?",
                (rs, row) -> rs.getString(1), proposalId);
        if (!existing.isEmpty()) {
            return List.of(existing.get(0).split(","));
        }
        List<String> ids = new ArrayList<>();
        for (String title : titles) {
            String taskId = ident("TASK-");
            jdbc.update("""
                    INSERT INTO episode_task (task_id, episode_id, title, status, kind, proposal_id, created_at)
                    VALUES (?, ?, ?, 'open', 'follow_up', ?, ?)
                    """, taskId, episodeId, title, proposalId, now());
            ids.add(taskId);
        }
        jdbc.update(
                "INSERT INTO follow_up_grant (proposal_id, episode_id, task_ids) VALUES (?, ?, ?)",
                proposalId, episodeId, String.join(",", ids));
        bump(episodeId, expectedVersion);
        audit(episodeId, actorId, "follow_up_created", "recorded", proposalId);
        return List.copyOf(ids);
    }

    @Transactional
    public void close(String episodeId, int expectedVersion, String actorId) {
        requireOpen(episodeId, expectedVersion);
        int updated = jdbc.update("""
                UPDATE hospitalization
                SET status = 'closed', closed_at = ?, closed_by = ?, version = version + 1
                WHERE episode_id = ? AND version = ? AND status = 'open'
                """, now(), actorId, episodeId, expectedVersion);
        if (updated != 1) {
            throw new InpatientRejection("version_conflict", 409);
        }
        audit(episodeId, actorId, "episode_closed", "recorded", actorId);
    }

    public Map<String, Object> chart(String episodeId) {
        Map<String, Object> episode = episode(episodeId);
        List<Map<String, Object>> notes = new ArrayList<>();
        for (Map<String, Object> note : cast(episode.get("notes"))) {
            String body = String.valueOf(note.get("body"));
            boolean withheld = INJECTION.matcher(body).find();
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", note.get("note_id"));
            item.put("withheld", withheld);
            item.put("text", withheld ? "" : body);
            notes.add(item);
        }
        Map<String, Object> chart = new LinkedHashMap<>();
        chart.put("organizationId", episode.get("organization_id"));
        chart.put("patientId", episode.get("patient_id"));
        chart.put("episodeId", episode.get("episode_id"));
        chart.put("version", ((Number) episode.get("version")).intValue());
        chart.put("status", episode.get("status"));
        chart.put("notes", notes);
        chart.put("allergies", names(cast(episode.get("allergies")), "allergy_id", "substance"));
        chart.put("medications", medicationsForChart(cast(episode.get("medications"))));
        chart.put("tasks", tasksForChart(cast(episode.get("tasks"))));
        chart.put("results", resultsForChart(cast(episode.get("results"))));
        chart.put("contradictions", contradictions(cast(episode.get("medications"))));
        return chart;
    }

    private Map<String, Object> requireOpen(String episodeId, int expectedVersion) {
        ensure();
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT * FROM hospitalization WHERE episode_id = ?", episodeId);
        if (rows.isEmpty()) {
            throw new InpatientRejection("episode_not_found", 404);
        }
        Map<String, Object> row = rows.get(0);
        if (!"open".equals(row.get("status"))) {
            throw new InpatientRejection("episode_not_open", 409);
        }
        if (((Number) row.get("version")).intValue() != expectedVersion) {
            throw new InpatientRejection("version_conflict", 409);
        }
        return row;
    }

    private void bump(String episodeId, int expectedVersion) {
        int updated = jdbc.update(
                "UPDATE hospitalization SET version = version + 1 WHERE episode_id = ? AND version = ? AND status = 'open'",
                episodeId, expectedVersion);
        if (updated != 1) {
            throw new InpatientRejection("version_conflict", 409);
        }
    }

    private List<Map<String, Object>> notes(String episodeId) {
        return jdbc.queryForList(
                "SELECT note_id, author_id, body, created_at FROM evolution_note WHERE episode_id = ? ORDER BY created_at",
                episodeId);
    }

    private List<Map<String, Object>> tasks(String episodeId) {
        return jdbc.queryForList(
                "SELECT task_id, title, status, kind, proposal_id, created_at FROM episode_task WHERE episode_id = ? ORDER BY created_at",
                episodeId);
    }

    private List<Map<String, Object>> linkedResults(String episodeId) {
        return jdbc.queryForList("""
                SELECT r.result_id, r.display_name, r.value_text, r.unit
                FROM episode_result er
                JOIN clinical_result r ON r.result_id = er.result_id
                WHERE er.episode_id = ?
                ORDER BY r.result_id
                """, episodeId);
    }

    private List<Map<String, Object>> availableResults(String patientId) {
        return jdbc.queryForList("""
                SELECT result_id, display_name, value_text, unit
                FROM clinical_result
                WHERE patient_id = ? AND result_type = 'laboratory'
                ORDER BY result_id
                """, patientId);
    }

    private List<Map<String, Object>> allergies(String patientId) {
        return jdbc.queryForList(
                "SELECT allergy_id, substance, recorded_at FROM allergy_record WHERE patient_id = ? ORDER BY recorded_at",
                patientId);
    }

    private List<Map<String, Object>> medications(String patientId) {
        return jdbc.queryForList("""
                SELECT medication_id, name, documented_status, recorded_at
                FROM medication_statement WHERE patient_id = ? ORDER BY recorded_at
                """, patientId);
    }

    private Map<String, Object> proposal(String episodeId) {
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT proposal_id, proposal_hash, episode_version, phase, checklist_complete, body_json FROM discharge_view WHERE episode_id = ?",
                episodeId);
        return rows.isEmpty() ? Map.of() : rows.get(0);
    }

    private List<Map<String, Object>> auditRows(String episodeId) {
        return jdbc.queryForList("""
                SELECT actor_id, action, outcome, detail, recorded_at
                FROM inpatient_audit WHERE episode_id = ? ORDER BY audit_id
                """, episodeId);
    }

    private List<Map<String, Object>> timeline(Map<String, Object> episode) {
        List<Map<String, Object>> events = new ArrayList<>();
        events.add(event(String.valueOf(episode.get("opened_at")), "Hospitalización abierta"));
        for (Map<String, Object> note : cast(episode.get("notes"))) {
            events.add(event(String.valueOf(note.get("created_at")), "Nota " + note.get("note_id")));
        }
        for (Map<String, Object> task : cast(episode.get("tasks"))) {
            events.add(event(String.valueOf(task.get("created_at")), "Tarea " + task.get("task_id") + " " + task.get("status")));
        }
        for (Map<String, Object> row : cast(episode.get("audit"))) {
            events.add(event(String.valueOf(row.get("recorded_at")), row.get("action") + " " + row.get("outcome")));
        }
        return events;
    }

    private Map<String, Object> checklist(Map<String, Object> episode) {
        boolean notes = !cast(episode.get("notes")).isEmpty();
        boolean results = !cast(episode.get("results")).isEmpty();
        boolean allergies = !cast(episode.get("allergies")).isEmpty();
        List<Map<String, Object>> medications = cast(episode.get("medications"));
        boolean medicationsOk = !medications.isEmpty() && contradictions(medications).isEmpty();
        boolean pendingClear = cast(episode.get("tasks")).stream()
                .noneMatch(task -> "ward".equals(task.get("kind")) && "open".equals(task.get("status")));
        boolean documented = "accepted".equals(episode.get("documentation_status"));
        Map<String, Object> list = new LinkedHashMap<>();
        list.put("notes", notes);
        list.put("results", results);
        list.put("allergies", allergies);
        list.put("medications", medicationsOk);
        list.put("pending", pendingClear);
        list.put("documentation", documented);
        list.put("complete", notes && results && allergies && medicationsOk && pendingClear && documented);
        return list;
    }

    private List<String> contradictions(List<Map<String, Object>> medications) {
        Map<String, String> seen = new LinkedHashMap<>();
        List<String> found = new ArrayList<>();
        for (Map<String, Object> medication : medications) {
            String name = String.valueOf(medication.get("name")).toLowerCase(Locale.ROOT);
            String status = String.valueOf(medication.get("documented_status"));
            String previous = seen.putIfAbsent(name, status);
            if (previous != null && !previous.equals(status)) {
                found.add(name);
            }
        }
        return found;
    }

    private List<Map<String, Object>> names(List<Map<String, Object>> rows, String id, String label) {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            items.add(Map.of("id", row.get(id), "substance", row.get(label)));
        }
        return items;
    }

    private List<Map<String, Object>> medicationsForChart(List<Map<String, Object>> rows) {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", row.get("medication_id"));
            item.put("name", row.get("name"));
            item.put("status", row.get("documented_status"));
            items.add(item);
        }
        return items;
    }

    private List<Map<String, Object>> tasksForChart(List<Map<String, Object>> rows) {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", row.get("task_id"));
            item.put("title", row.get("title"));
            item.put("status", row.get("status"));
            item.put("kind", row.get("kind"));
            items.add(item);
        }
        return items;
    }

    private List<Map<String, Object>> resultsForChart(List<Map<String, Object>> rows) {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", row.get("result_id"));
            item.put("name", row.get("display_name"));
            item.put("value", row.get("value_text"));
            item.put("unit", row.get("unit"));
            items.add(item);
        }
        return items;
    }

    private void audit(String episodeId, String actorId, String action, String outcome, String detail) {
        jdbc.update("""
                INSERT INTO inpatient_audit (episode_id, actor_id, action, outcome, detail, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """, episodeId, actorId, action, outcome, detail, now());
    }

    private static Map<String, Object> event(String at, String label) {
        return Map.of("at", at, "label", label);
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> cast(Object value) {
        return value instanceof List<?> list ? (List<Map<String, Object>>) list : List.of();
    }

    private static String requiredText(String value) {
        if (value == null || !SAFE_TEXT.matcher(value.trim()).matches()) {
            throw new InpatientRejection("invalid_input", 400);
        }
        return value.trim();
    }

    private static String ident(String prefix) {
        return prefix + UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase(Locale.ROOT);
    }

    private static String now() {
        return Instant.now().toString();
    }
}
