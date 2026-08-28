package lab.healthcare.fhir.observability;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentLinkedDeque;

/**
 * Lab recorder: structured SLF4J line plus a bounded in-memory buffer.
 * Not a database and not a SIEM.
 */
@Component
public class LoggingFhirAuditRecorder implements FhirAuditRecorder {

    static final int MAX_EVENTS = 100;

    private static final Logger log = LoggerFactory.getLogger(LoggingFhirAuditRecorder.class);

    private final ConcurrentLinkedDeque<FhirAuditEvent> events = new ConcurrentLinkedDeque<>();

    @Override
    public void record(FhirAuditEvent event) {
        if (event == null) {
            throw new IllegalArgumentException("Audit event must be provided");
        }
        events.addLast(event);
        while (events.size() > MAX_EVENTS) {
            events.pollFirst();
        }
        log.info("{}", event.toLogLine());
    }

    public List<FhirAuditEvent> recorded() {
        return List.copyOf(new ArrayList<>(events));
    }
}
