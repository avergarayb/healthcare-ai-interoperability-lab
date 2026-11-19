package lab.healthcare.minilis;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@Service
public class BenchWorkflow {

    private final JdbcTemplate jdbc;
    private final LaboratoryRecordService records;

    public BenchWorkflow(JdbcTemplate jdbc, LaboratoryRecordService records) {
        this.jdbc = jdbc;
        this.records = records;
    }

    public Optional<BenchCase> find(String orderId) {
        List<BenchCase> rows = jdbc.query(
                """
                SELECT order_id, state, specimen_id, draft_value, draft_unit, draft_note, result_id, publication
                FROM specimen_case WHERE order_id = ?
                """,
                (rs, row) -> new BenchCase(
                        rs.getString("order_id"),
                        rs.getString("state"),
                        rs.getString("specimen_id"),
                        rs.getString("draft_value"),
                        rs.getString("draft_unit"),
                        rs.getString("draft_note"),
                        rs.getString("result_id"),
                        rs.getString("publication")),
                orderId);
        return rows.stream().findFirst();
    }

    public String stateOf(String orderId) {
        return find(orderId).map(BenchCase::state).orElse("ORDER_RECEIVED");
    }

    public Optional<Map<String, Object>> criticalEvent(String orderId) {
        List<Map<String, Object>> rows = jdbc.queryForList(
                """
                SELECT event_id, order_id, result_id, patient_id, organization_id, correlation_id,
                       rule_id, rule_version, test_code, original_value, current_value, unit, status,
                       recorded_at, corrected_at
                FROM critical_event WHERE order_id = ?
                """,
                orderId);
        return rows.stream().findFirst();
    }

    public List<Map<String, Object>> criticalEvents() {
        return jdbc.queryForList("""
                SELECT event_id, order_id, correlation_id, rule_id, rule_version, current_value, unit, status, recorded_at
                FROM critical_event ORDER BY recorded_at DESC LIMIT 50
                """);
    }

    @Transactional
    public BenchCase advance(String orderId, String action, String value, String unit, String note, boolean validator) {
        LabOrder order = records.order(orderId);
        BenchCase current = find(orderId).orElse(null);
        String state = current == null ? "ORDER_RECEIVED" : current.state();
        String now = OffsetDateTime.now(ZoneOffset.UTC).toString();
        return switch (action) {
            case "register" -> move(order, current, state, "ORDER_RECEIVED", "SPECIMEN_REGISTERED", null, null, null, now);
            case "receive" -> move(order, current, state, "SPECIMEN_REGISTERED", "SPECIMEN_RECEIVED", null, null, null, now);
            case "process" -> move(order, current, state, "SPECIMEN_RECEIVED", "PROCESSING", null, null, null, now);
            case "draft" -> draft(order, current, state, value, unit, note, now);
            case "validate" -> validate(current, state, validator, now);
            case "publish" -> publish(order, current, state, validator, now);
            case "correct" -> correct(order, current, state, value, validator, now);
            default -> throw MiniLisException.invalidTransition();
        };
    }

    private BenchCase move(
            LabOrder order, BenchCase current, String state, String expected, String next,
            String value, String unit, String note, String now) {
        if (!expected.equals(state)) {
            throw MiniLisException.invalidTransition();
        }
        String specimenId = current != null && current.specimenId() != null
                ? current.specimenId()
                : "MLS-SPC-" + suffix();
        save(order.orderId(), next, specimenId, value, unit, note, null, null, now);
        return find(order.orderId()).orElseThrow();
    }

    private BenchCase draft(LabOrder order, BenchCase current, String state, String value, String unit, String note, String now) {
        if (!"PROCESSING".equals(state) && !"DRAFT".equals(state)) {
            throw MiniLisException.invalidTransition();
        }
        String cleanValue = requireValue(value);
        String cleanUnit = requireUnit(order.testCode(), unit);
        String cleanNote = cleanNote(note);
        String specimenId = current == null ? "MLS-SPC-" + suffix() : current.specimenId();
        save(order.orderId(), "DRAFT", specimenId, cleanValue, cleanUnit, cleanNote, null, null, now);
        return find(order.orderId()).orElseThrow();
    }

    private BenchCase validate(BenchCase current, String state, boolean validator, String now) {
        if (!validator) {
            throw MiniLisException.unauthorized();
        }
        if (!"DRAFT".equals(state) || current == null) {
            throw MiniLisException.invalidTransition();
        }
        save(current.orderId(), "VALIDATED", current.specimenId(), current.draftValue(), current.draftUnit(),
                current.draftNote(), null, null, now);
        return find(current.orderId()).orElseThrow();
    }

    private BenchCase publish(LabOrder order, BenchCase current, String state, boolean validator, String now) {
        if (!validator) {
            throw MiniLisException.unauthorized();
        }
        if (current != null && "PUBLISHED".equals(current.state())) {
            return current;
        }
        if (!"VALIDATED".equals(state) || current == null) {
            throw MiniLisException.invalidTransition();
        }
        String externalId = "BENCH-" + order.orderId();
        LabResult existing = records.resultsForOrder(order.orderId()).stream()
                .filter(result -> externalId.equals(result.externalResultId()))
                .findFirst()
                .orElse(null);
        LabResult stored = existing == null
                ? records.recordResult(new NewResult(
                        order.orderId(),
                        externalId,
                        order.testCode(),
                        current.draftValue(),
                        current.draftUnit(),
                        referenceFor(order.testCode()),
                        OffsetDateTime.now(ZoneOffset.UTC),
                        ResultStatus.FINAL))
                : existing;
        String publication = "queued";
        save(order.orderId(), "PUBLISHED", current.specimenId(), current.draftValue(), current.draftUnit(),
                current.draftNote(), stored.resultId(), publication, now);
        rememberCritical(order, stored, current.draftValue(), now);
        return find(order.orderId()).orElseThrow();
    }

    private BenchCase correct(LabOrder order, BenchCase current, String state, String value, boolean validator, String now) {
        if (!validator) {
            throw MiniLisException.unauthorized();
        }
        if (!"PUBLISHED".equals(state) || current == null || current.resultId() == null) {
            throw MiniLisException.invalidTransition();
        }
        String cleanValue = requireValue(value);
        String externalId = "BENCH-CORR-" + order.orderId();
        boolean already = records.resultsForOrder(order.orderId()).stream()
                .anyMatch(result -> externalId.equals(result.externalResultId()));
        if (!already) {
            records.recordResult(new NewResult(
                    order.orderId(),
                    externalId,
                    order.testCode(),
                    cleanValue,
                    current.draftUnit(),
                    referenceFor(order.testCode()),
                    OffsetDateTime.now(ZoneOffset.UTC),
                    ResultStatus.FINAL));
        }
        jdbc.update(
                """
                UPDATE critical_event
                SET current_value = ?, corrected_at = ?, status = 'corrected'
                WHERE order_id = ?
                """,
                cleanValue, now, order.orderId());
        save(order.orderId(), "PUBLISHED", current.specimenId(), cleanValue, current.draftUnit(),
                current.draftNote(), current.resultId(), current.publication(), now);
        return find(order.orderId()).orElseThrow();
    }

    private void rememberCritical(LabOrder order, LabResult result, String value, String now) {
        if (!CriticalRule.matches(order.testCode(), result.unit(), value)) {
            return;
        }
        if (criticalEvent(order.orderId()).isPresent()) {
            return;
        }
        jdbc.update(
                """
                INSERT INTO critical_event (
                    event_id, order_id, result_id, patient_id, organization_id, correlation_id,
                    rule_id, rule_version, test_code, original_value, current_value, unit, status, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
                """,
                "MLS-CRT-" + suffix(),
                order.orderId(),
                result.resultId(),
                order.patientId(),
                order.requestingOrganizationId(),
                order.externalRequestId(),
                CriticalRule.ID,
                CriticalRule.VERSION,
                order.testCode(),
                value,
                value,
                result.unit(),
                now);
    }

    private void save(
            String orderId, String state, String specimenId, String value, String unit, String note,
            String resultId, String publication, String now) {
        jdbc.update("DELETE FROM specimen_case WHERE order_id = ?", orderId);
        jdbc.update(
                """
                INSERT INTO specimen_case (
                    order_id, state, specimen_id, draft_value, draft_unit, draft_note, result_id, publication, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                orderId, state, specimenId, value, unit, note, resultId, publication, now);
    }

    private static String requireValue(String value) {
        if (value == null || !value.trim().matches("[0-9]+(?:\\.[0-9]+)?")) {
            throw MiniLisException.invalidRequest();
        }
        return value.trim();
    }

    private static String requireUnit(String testCode, String unit) {
        String clean = unit == null ? "" : unit.trim();
        boolean allowed = ("718-7".equals(testCode) && "g/dL".equals(clean))
                || ("GLU".equals(testCode) && "mg/dL".equals(clean));
        if (!allowed) {
            throw MiniLisException.invalidRequest();
        }
        return clean;
    }

    private static String referenceFor(String testCode) {
        return "718-7".equals(testCode) ? "12.0-16.0" : "70-110";
    }

    private static String cleanNote(String note) {
        if (note == null || note.isBlank()) {
            return "";
        }
        String trimmed = note.trim();
        if (trimmed.length() > 240) {
            throw MiniLisException.invalidRequest();
        }
        return trimmed;
    }

    private static String suffix() {
        return UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase(Locale.ROOT);
    }

    public record BenchCase(
            String orderId,
            String state,
            String specimenId,
            String draftValue,
            String draftUnit,
            String draftNote,
            String resultId,
            String publication) {
    }
}
