package lab.healthcare.fhir.exchange;

import lab.healthcare.fhir.interop.SourceRegistry;
import lab.healthcare.fhir.interop.SourceRegistry.SourceDescriptor;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.ZoneOffset;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.UUID;
import java.util.regex.Pattern;

/**
 * Cross-organization order exchange. The caller system comes from the
 * authenticated participant. Destination selection uses the source registry
 * and the connector list, not a fixed pair of systems.
 */
public class ExchangeService {

    private static final Logger log = LoggerFactory.getLogger(ExchangeService.class);
    private static final Pattern ID = Pattern.compile("[A-Za-z0-9\\-.]{1,64}");
    private static final Pattern SYSTEM = Pattern.compile("https://[A-Za-z0-9./_-]{1,200}");

    private final SourceRegistry registry;
    private final ExchangeStore store;
    private final List<OrderDestination> orderDestinations;
    private final List<ResultSource> resultSources;
    private final CanonicalServiceRequestFactory fhir;

    public ExchangeService(
            SourceRegistry registry,
            ExchangeStore store,
            List<OrderDestination> orderDestinations,
            List<ResultSource> resultSources,
            ObjectMapper json) {
        this.registry = registry;
        this.store = store;
        this.orderDestinations = List.copyOf(orderDestinations);
        this.resultSources = List.copyOf(resultSources);
        this.fhir = new CanonicalServiceRequestFactory(json);
    }

    public ExchangeReceipt submit(String callerSystem, OrderSubmission submission) {
        SourceDescriptor source = requireCaller(callerSystem, submission.sourceOrganizationId());
        SourceDescriptor destination = requireDestination(source, submission.destinationSystemKey());
        validate(submission);
        OrderDestination connector = orderDestinations.stream()
                .filter(candidate -> candidate.systemKey().equals(destination.key()))
                .findFirst()
                .orElseThrow(ExchangeException::notRoutable);

        OrderCorrelation existing = store.findOrder(
                source.key(), source.organizationId(), submission.externalRequestId(), destination.key())
                .orElse(null);
        if (existing != null && existing.destinationOrderId() != null) {
            log.info("exchange_order_duplicate correlation={} sourceOrder={}", existing.correlationId(), existing.sourceOrderId());
            return receipt(existing, source, destination, "duplicate", null, null, null);
        }

        String correlationId = existing == null ? newId() : existing.correlationId();
        OrderCorrelation pending = correlation(correlationId, source, destination, submission, null, null, "pending", null);
        if (existing == null) {
            store.insert(pending);
        }

        try {
            String knownDestinationPatientId;
            String commandPatientId;
            if (connector.embedsPatientInOrder()) {
                connector.resolvePatient(source.organizationId(), submission.patient());
                knownDestinationPatientId = store.findPatientLink(
                        source.key(),
                        submission.patient().identifierSystem(),
                        submission.patient().identifierValue(),
                        destination.key()).orElse(null);
                commandPatientId = knownDestinationPatientId == null
                        ? submission.patient().identifierValue()
                        : knownDestinationPatientId;
            } else {
                knownDestinationPatientId = resolvePatient(source, destination, connector, submission.patient());
                commandPatientId = knownDestinationPatientId;
            }
            OrderCorrelation linked = correlation(
                    correlationId, source, destination, submission, null, knownDestinationPatientId, "pending", null);
            ObjectNode serviceRequest = fhir.create(linked, source, destination);
            DestinationCommand command = fhir.command(serviceRequest, commandPatientId);
            AcceptedOrder accepted = connector.accept(command);
            String destinationPatientId = accepted.patientId() != null ? accepted.patientId() : knownDestinationPatientId;
            if (accepted.patientId() != null) {
                store.savePatientLink(
                        source.key(),
                        submission.patient().identifierSystem(),
                        submission.patient().identifierValue(),
                        destination.key(),
                        accepted.patientId());
            }
            String state = accepted.alreadyPresent() ? "duplicate" : "accepted";
            store.updateDelivery(correlationId, state, null, accepted.orderId(), destinationPatientId);
            OrderCorrelation stored = reload(source, destination, submission.externalRequestId());
            log.info(
                    "exchange_order_accepted correlation={} sourceOrder={} destinationOrder={} state={}",
                    stored.correlationId(),
                    stored.sourceOrderId(),
                    stored.destinationOrderId(),
                    state);
            return receipt(stored, source, destination, state, null, null, null);
        } catch (ExchangeException ex) {
            String state = ex.status() >= 500 ? "destination_unavailable" : "rejected";
            store.updateDelivery(correlationId, state, ex.code(), null, null);
            log.info("exchange_order_failed correlation={} error={}", correlationId, ex.code());
            throw ex.withCorrelation(correlationId);
        }
    }

    public ExchangeReceipt report(String callerSystem, String sourceOrderId) {
        if (sourceOrderId == null || !ID.matcher(sourceOrderId).matches()) {
            throw ExchangeException.invalidRequest();
        }
        SourceDescriptor source = registry.find(callerSystem).orElseThrow(ExchangeException::forbidden);
        OrderCorrelation correlation = store.findOwnedOrder(source.key(), sourceOrderId)
                .orElseThrow(ExchangeException::notFound);
        if (correlation.destinationOrderId() == null) {
            throw ExchangeException.unavailable().withCorrelation(correlation.correlationId());
        }
        SourceDescriptor destination = registry.find(correlation.destinationSystem())
                .orElseThrow(ExchangeException::notRoutable);
        ResultSource reader = resultSources.stream()
                .filter(candidate -> candidate.systemKey().equals(destination.key()))
                .findFirst()
                .orElseThrow(ExchangeException::notRoutable);
        DestinationReport report;
        try {
            report = reader.read(correlation.destinationOrderId());
        } catch (ExchangeException ex) {
            log.info("exchange_report_failed correlation={} error={}", correlation.correlationId(), ex.code());
            throw ex.withCorrelation(correlation.correlationId());
        }
        log.info("exchange_report_read correlation={} sourceOrder={}", correlation.correlationId(), correlation.sourceOrderId());
        return receipt(
                correlation,
                source,
                destination,
                correlation.deliveryState(),
                report.serviceRequest(),
                report.diagnosticReport(),
                report.observations());
    }

    private String resolvePatient(
            SourceDescriptor source,
            SourceDescriptor destination,
            OrderDestination connector,
            PatientIdentity patient) {
        Optional<String> linked = store.findPatientLink(
                source.key(), patient.identifierSystem(), patient.identifierValue(), destination.key());
        if (linked.isPresent()) {
            return linked.get();
        }
        String destinationPatientId = connector.resolvePatient(source.organizationId(), patient);
        if (destinationPatientId == null || !ID.matcher(destinationPatientId).matches()) {
            throw ExchangeException.unavailable();
        }
        store.savePatientLink(
                source.key(),
                patient.identifierSystem(),
                patient.identifierValue(),
                destination.key(),
                destinationPatientId);
        return destinationPatientId;
    }

    private SourceDescriptor requireCaller(String callerSystem, String sourceOrganizationId) {
        SourceDescriptor source = registry.find(callerSystem).orElseThrow(ExchangeException::forbidden);
        if (sourceOrganizationId == null || !source.organizationId().equals(sourceOrganizationId)) {
            throw ExchangeException.forbidden();
        }
        return source;
    }

    private SourceDescriptor requireDestination(SourceDescriptor source, String destinationSystemKey) {
        if (destinationSystemKey == null || destinationSystemKey.equals(source.key())) {
            throw ExchangeException.notRoutable();
        }
        SourceDescriptor destination = registry.find(destinationSystemKey).orElseThrow(ExchangeException::notRoutable);
        if (!destination.capabilities().contains("service-request")) {
            throw ExchangeException.notRoutable();
        }
        return destination;
    }

    private static void validate(OrderSubmission submission) {
        PatientIdentity patient = submission.patient();
        if (patient == null
                || !ID.matcher(empty(submission.externalRequestId())).matches()
                || !ID.matcher(empty(submission.testCode())).matches()
                || submission.testDescription() == null
                || submission.testDescription().isBlank()
                || submission.testDescription().length() > 200
                || submission.requestedAt() == null
                || !SYSTEM.matcher(empty(patient.identifierSystem())).matches()
                || !ID.matcher(empty(patient.identifierValue())).matches()
                || patient.familyName() == null
                || patient.familyName().isBlank()
                || patient.givenName() == null
                || patient.givenName().isBlank()
                || patient.birthDate() == null
                || !List.of("female", "male", "unknown").contains(empty(patient.administrativeSex()))) {
            throw ExchangeException.invalidRequest();
        }
    }

    private OrderCorrelation reload(SourceDescriptor source, SourceDescriptor destination, String sourceOrderId) {
        return store.findOrder(source.key(), source.organizationId(), sourceOrderId, destination.key())
                .orElseThrow(ExchangeException::unavailable);
    }

    private ExchangeReceipt receipt(
            OrderCorrelation correlation,
            SourceDescriptor source,
            SourceDescriptor destination,
            String state,
            JsonNode destinationServiceRequest,
            JsonNode diagnosticReport,
            List<JsonNode> observations) {
        ObjectNode serviceRequest = fhir.create(correlation, source, destination);
        return new ExchangeReceipt(
                correlation.correlationId(),
                state,
                new ExchangeParty(source.key(), source.organizationId(), correlation.sourceOrderId(), null),
                new ExchangeParty(
                        destination.key(),
                        destination.organizationId(),
                        correlation.destinationOrderId(),
                        correlation.destinationPatientId()),
                serviceRequest,
                destinationServiceRequest,
                diagnosticReport,
                observations == null ? List.of() : observations);
    }

    private static OrderCorrelation correlation(
            String correlationId,
            SourceDescriptor source,
            SourceDescriptor destination,
            OrderSubmission submission,
            String destinationOrderId,
            String destinationPatientId,
            String state,
            String errorCode) {
        return new OrderCorrelation(
                correlationId,
                source.key(),
                source.organizationId(),
                submission.externalRequestId(),
                destination.key(),
                destination.organizationId(),
                destinationOrderId,
                destinationPatientId,
                submission.patient().identifierSystem(),
                submission.patient().identifierValue(),
                submission.testCode(),
                submission.testDescription().trim(),
                submission.requestedAt().withOffsetSameInstant(ZoneOffset.UTC),
                state,
                errorCode);
    }

    private String newId() {
        return "EXC-" + UUID.randomUUID().toString().replace("-", "").substring(0, 16).toUpperCase(Locale.ROOT);
    }

    private static String empty(String value) {
        return value == null ? "" : value;
    }
}
