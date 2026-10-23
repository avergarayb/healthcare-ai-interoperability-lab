package lab.healthcare.minilis;

import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Clock;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.UUID;
import java.util.regex.Pattern;

/**
 * The only writer for laboratory patients, orders, and results.
 * The proprietary REST API and the HL7 v2 listener both call this service.
 * The listener does not write SQL of its own.
 */
@Service
public class LaboratoryRecordService {

    private static final Pattern ID = Pattern.compile("[A-Za-z0-9\\-.]{1,64}");

    private final LaboratoryRepository repository;
    private final Clock clock;
    private final ApplicationEventPublisher events;
    private final TransactionTemplate nestedWork;

    public LaboratoryRecordService(
            LaboratoryRepository repository,
            Clock clock,
            ApplicationEventPublisher events,
            PlatformTransactionManager transactions) {
        this.repository = repository;
        this.clock = clock;
        this.events = events;
        this.nestedWork = new TransactionTemplate(transactions);
        this.nestedWork.setPropagationBehavior(TransactionDefinition.PROPAGATION_NESTED);
    }

    @Transactional
    public ExternalPatient registerPatient(NewPatient command) {
        return registerPatient(command, newId("MLS-PAT-"));
    }

    @Transactional
    public ExternalPatient registerPatient(NewPatient command, String patientId) {
        requireId(patientId);
        requireId(command.organizationId());
        requireId(command.externalId());
        requireText(command.familyName(), 80);
        requireText(command.givenName(), 80);
        if (command.birthDate() == null || !List.of("female", "male", "unknown").contains(command.administrativeSex())) {
            throw MiniLisException.invalidRequest();
        }
        ExternalPatient patient = new ExternalPatient(
                patientId,
                command.organizationId(),
                command.externalId(),
                command.familyName().trim(),
                command.givenName().trim(),
                command.birthDate(),
                command.administrativeSex());
        repository.insertPatient(patient, now());
        return patient;
    }

    public ExternalPatient patient(String patientId) {
        requireId(patientId);
        return repository.findPatient(patientId).orElseThrow(MiniLisException::notFound);
    }

    public List<ExternalPatient> searchPatients(String organizationId, String externalId) {
        requireId(organizationId);
        requireId(externalId);
        return repository.searchPatients(organizationId, externalId);
    }

    public List<ExternalPatient> listPatients(int limit) {
        return repository.listPatients(limit);
    }

    @Transactional
    public LabOrder createOrder(NewOrder command) {
        return createOrder(command, newId("MLS-ORD-"));
    }

    @Transactional
    public LabOrder createOrder(NewOrder command, String orderId) {
        requireId(orderId);
        requireId(command.patientId());
        requireId(command.requestingOrganizationId());
        requireId(command.externalRequestId());
        requireId(command.testCode());
        requireText(command.testDescription(), 200);
        if (command.requestedAt() == null) {
            throw MiniLisException.invalidRequest();
        }
        if (repository.findPatient(command.patientId()).isEmpty()) {
            throw MiniLisException.notFound();
        }
        LabOrder order = new LabOrder(
                orderId,
                command.patientId(),
                command.requestingOrganizationId(),
                command.externalRequestId(),
                command.testCode(),
                command.testDescription().trim(),
                command.requestedAt().withOffsetSameInstant(ZoneOffset.UTC),
                OrderStatus.ORDERED);
        repository.insertOrder(order, now());
        return order;
    }

    public LabOrder order(String orderId) {
        requireId(orderId);
        return repository.findOrder(orderId).orElseThrow(MiniLisException::notFound);
    }

    public LabOrder orderByExternalRequest(String requestingOrganizationId, String externalRequestId) {
        requireId(requestingOrganizationId);
        requireId(externalRequestId);
        return repository.findOrderByExternalRequest(requestingOrganizationId, externalRequestId)
                .orElseThrow(MiniLisException::notFound);
    }

    public List<LabOrder> listOrders(int limit) {
        return repository.listOrders(limit);
    }

    public List<LabOrder> ordersForPatient(String patientId) {
        patient(patientId);
        return repository.listOrdersForPatient(patientId);
    }

    @Transactional
    public LabResult recordResult(NewResult command) {
        return recordResult(command, newId("MLS-RES-"));
    }

    @Transactional
    public LabResult recordResult(NewResult command, String resultId) {
        requireId(resultId);
        requireId(command.orderId());
        requireId(command.externalResultId());
        requireId(command.testCode());
        requireText(command.value(), 80);
        if (command.unit() != null) {
            requireText(command.unit(), 40);
        }
        if (command.referenceRange() != null) {
            requireText(command.referenceRange(), 80);
        }
        if (command.resultedAt() == null || command.status() == null) {
            throw MiniLisException.invalidRequest();
        }
        LabOrder order = repository.findOrder(command.orderId()).orElseThrow(MiniLisException::notFound);
        if (command.resultedAt().isBefore(order.requestedAt())) {
            throw MiniLisException.invalidRequest();
        }
        OrderStatus next = OrderTransition.afterResult(order.status());
        LabResult result = new LabResult(
                resultId,
                command.orderId(),
                order.patientId(),
                command.externalResultId(),
                command.testCode(),
                command.value().trim(),
                blankToNull(command.unit()),
                blankToNull(command.referenceRange()),
                command.resultedAt().withOffsetSameInstant(ZoneOffset.UTC),
                command.status());
        repository.insertResult(result, now());
        if (next != order.status()) {
            repository.updateOrderStatus(order.orderId(), next);
        }
        events.publishEvent(new LabResultRecorded(result.orderId(), result.resultId()));
        return result;
    }

    @Transactional
    public Hl7Ack acceptOml(OmlOrder order) {
        Optional<Hl7Ack> stored = repository.findHl7Ack(order.messageControlId());
        if (stored.isPresent()) {
            return stored.get();
        }
        ExternalPatient patient = nested(this::resolvePatient, order);
        boolean duplicate = false;
        LabOrder created;
        try {
            created = nested(() -> createOrder(new NewOrder(
                    patient.patientId(),
                    order.organizationId(),
                    order.placerOrderId(),
                    order.testCode(),
                    order.testDescription(),
                    order.requestedAt())));
        } catch (MiniLisException ex) {
            if (!"duplicate".equals(ex.code())) {
                throw ex;
            }
            created = orderByExternalRequest(order.organizationId(), order.placerOrderId());
            duplicate = true;
        }
        Hl7Ack ack = Hl7Ack.accepted(created.orderId(), patient.patientId(), duplicate);
        repository.insertHl7Ack(order.messageControlId(), "OML_O21", ack, order.placerOrderId(), now());
        return ack;
    }

    @Transactional
    public Hl7Ack rememberRejection(String messageControlId, String placerOrderId, String code, String detail) {
        Optional<Hl7Ack> stored = repository.findHl7Ack(messageControlId);
        if (stored.isPresent()) {
            return stored.get();
        }
        Hl7Ack ack = Hl7Ack.error(code, detail);
        repository.insertHl7Ack(messageControlId, "OML_O21", ack, placerOrderId, now());
        return ack;
    }

    private ExternalPatient resolvePatient(OmlOrder order) {
        List<ExternalPatient> found = searchPatients(order.organizationId(), order.externalPatientId());
        if (!found.isEmpty()) {
            return found.get(0);
        }
        try {
            return nested(() -> registerPatient(new NewPatient(
                    order.organizationId(),
                    order.externalPatientId(),
                    order.familyName(),
                    order.givenName(),
                    order.birthDate(),
                    order.administrativeSex())));
        } catch (MiniLisException ex) {
            if (!"duplicate".equals(ex.code())) {
                throw ex;
            }
            return searchPatients(order.organizationId(), order.externalPatientId()).get(0);
        }
    }

    public LabResult result(String resultId) {
        requireId(resultId);
        return repository.findResult(resultId).orElseThrow(MiniLisException::notFound);
    }

    public List<LabResult> resultsForOrder(String orderId) {
        order(orderId);
        return repository.listResultsForOrder(orderId);
    }

    public List<LabResult> resultsForPatient(String patientId) {
        patient(patientId);
        return repository.listResultsForPatient(patientId);
    }

    @Transactional
    public LabOrder complete(String orderId) {
        LabOrder order = order(orderId);
        if (order.status() == OrderStatus.COMPLETED) {
            return order;
        }
        OrderTransition.requireCompletable(order.status(), repository.hasFinalResult(orderId));
        repository.updateOrderStatus(orderId, OrderStatus.COMPLETED);
        return this.order(orderId);
    }

    @Transactional
    public LabOrder cancel(String orderId) {
        LabOrder order = order(orderId);
        if (order.status() == OrderStatus.CANCELLED) {
            return order;
        }
        OrderTransition.requireCancellable(order.status(), repository.hasFinalResult(orderId));
        repository.updateOrderStatus(orderId, OrderStatus.CANCELLED);
        return this.order(orderId);
    }

    public int storedPatients() {
        return repository.countPatients();
    }

    private <T> T nested(java.util.function.Supplier<T> action) {
        return nestedWork.execute(status -> action.get());
    }

    private ExternalPatient nested(java.util.function.Function<OmlOrder, ExternalPatient> action, OmlOrder order) {
        return nestedWork.execute(status -> action.apply(order));
    }

    private OffsetDateTime now() {
        return OffsetDateTime.now(clock).withOffsetSameInstant(ZoneOffset.UTC);
    }

    private static String newId(String prefix) {
        return prefix + UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase(Locale.ROOT);
    }

    private static void requireId(String value) {
        if (value == null || !ID.matcher(value).matches()) {
            throw MiniLisException.invalidRequest();
        }
    }

    private static void requireText(String value, int max) {
        if (value == null || value.isBlank() || value.trim().length() > max) {
            throw MiniLisException.invalidRequest();
        }
    }

    private static String blankToNull(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }
}
