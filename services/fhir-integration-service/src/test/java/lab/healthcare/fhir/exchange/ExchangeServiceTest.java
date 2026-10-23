package lab.healthcare.fhir.exchange;

import lab.healthcare.fhir.interop.InteropSourcesProperties;
import lab.healthcare.fhir.interop.SourceRegistry;

import ca.uhn.fhir.context.FhirContext;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ExchangeServiceTest {

    private final ObjectMapper json = new ObjectMapper();
    private final MemoryStore store = new MemoryStore();
    private final FakeDestination destination = new FakeDestination();
    private final ExchangeService exchange = new ExchangeService(
            registry(), store, List.of(destination), List.of(destination), json);

    @Test
    void sameIdentifierReusesThePatientAndARepeatedOrderDoesNotCreateAnother() {
        ExchangeReceipt first = exchange.submit("mini-his", submission("MHS-PAT-001", "MHS-LAB-001", "Ana"));
        ExchangeReceipt renamed = exchange.submit("mini-his", submission("MHS-PAT-001", "MHS-LAB-002", "Other"));
        ExchangeReceipt repeated = exchange.submit("mini-his", submission("MHS-PAT-001", "MHS-LAB-001", "Ana"));

        assertThat(destination.patientLookups).containsExactly("org-mini-his|MHS-PAT-001");
        assertThat(renamed.destination().patientId()).isEqualTo(first.destination().patientId());
        assertThat(destination.orderPosts).isEqualTo(2);
        assertThat(repeated.deliveryState()).isEqualTo("duplicate");
        assertThat(repeated.destination().orderId()).isEqualTo(first.destination().orderId());
        assertThat(destination.orderPosts).isEqualTo(2);
        assertThat(first.serviceRequest().toString()).doesNotContain("loinc").doesNotContain("Ana");
        FhirContext.forR4().newJsonParser().parseResource(first.serviceRequest().toString());
    }

    @Test
    void theSameNameWithAnotherIdentifierCreatesAnotherPatient() {
        ExchangeReceipt first = exchange.submit("mini-his", submission("MHS-PAT-001", "MHS-LAB-010", "Ana"));
        ExchangeReceipt second = exchange.submit("mini-his", submission("MHS-PAT-009", "MHS-LAB-011", "Ana"));
        assertThat(second.destination().patientId()).isNotEqualTo(first.destination().patientId());
        assertThat(destination.patientLookups).containsExactly("org-mini-his|MHS-PAT-001", "org-mini-his|MHS-PAT-009");
    }

    @Test
    void aCallerCannotSubmitUnderAnotherOrganizationsIdentity() {
        assertThatThrownBy(() -> exchange.submit("clinic-b", submission("MHS-PAT-001", "MHS-LAB-050", "Ana")))
                .isInstanceOf(ExchangeException.class)
                .extracting(throwable -> ((ExchangeException) throwable).code())
                .isEqualTo("organization_forbidden");
        OrderSubmission claimed = new OrderSubmission(
                "org-clinic-b",
                "mini-lis",
                "MHS-LAB-051",
                "GLU",
                "Glucose",
                OffsetDateTime.parse("2026-03-01T10:00:00Z"),
                new PatientIdentity(
                        "https://lab.local/mini-his/patient",
                        "MHS-PAT-001",
                        "Quispe",
                        "Ana",
                        LocalDate.parse("1984-03-12"),
                        "female"));
        assertThatThrownBy(() -> exchange.submit("mini-his", claimed))
                .isInstanceOf(ExchangeException.class)
                .extracting(throwable -> ((ExchangeException) throwable).code())
                .isEqualTo("organization_forbidden");
        assertThat(destination.orderPosts).isZero();
        assertThat(destination.patientLookups).isEmpty();
    }

    @Test
    void anotherOrganizationCannotReadTheOrderAndAnUnconnectedDestinationIsNotCalled() {
        ExchangeReceipt created = exchange.submit("mini-his", submission("MHS-PAT-001", "MHS-LAB-020", "Ana"));
        assertThatThrownBy(() -> exchange.report("clinic-b", created.source().orderId()))
                .isInstanceOf(ExchangeException.class)
                .extracting(throwable -> ((ExchangeException) throwable).code())
                .isEqualTo("not_found");
        assertThatThrownBy(() -> exchange.submit("mini-his", submissionTo("clinic-b", "MHS-PAT-001", "MHS-LAB-021")))
                .isInstanceOf(ExchangeException.class)
                .extracting(throwable -> ((ExchangeException) throwable).code())
                .isEqualTo("destination_not_routable");
        assertThat(destination.orderPosts).isEqualTo(1);
    }

    @Test
    void aLostAcceptanceIsRecoveredWithoutASecondOrder() {
        destination.alreadyStored.put("org-mini-his|MHS-LAB-030", "MLS-ORD-RECOVERED");
        ExchangeReceipt receipt = exchange.submit("mini-his", submission("MHS-PAT-001", "MHS-LAB-030", "Ana"));
        assertThat(receipt.deliveryState()).isEqualTo("duplicate");
        assertThat(receipt.destination().orderId()).isEqualTo("MLS-ORD-RECOVERED");
        assertThat(destination.createdOrders).doesNotContain("MLS-ORD-RECOVERED");
    }

    @Test
    void destinationFailureKeepsTheCorrelationAndARetryCanSucceed() {
        destination.failNext = true;
        OrderSubmission submission = submission("MHS-PAT-001", "MHS-LAB-040", "Ana");
        ExchangeException failed = org.assertj.core.api.Assertions.catchThrowableOfType(
                () -> exchange.submit("mini-his", submission), ExchangeException.class);
        assertThat(failed.code()).isEqualTo("destination_unavailable");
        assertThat(failed.correlationId()).startsWith("EXC-");
        assertThatThrownBy(() -> exchange.report("mini-his", submission.externalRequestId()))
                .isInstanceOf(ExchangeException.class)
                .extracting(throwable -> ((ExchangeException) throwable).code())
                .isEqualTo("destination_unavailable");
        ExchangeReceipt retried = exchange.submit("mini-his", submission);
        assertThat(retried.correlationId()).isEqualTo(failed.correlationId());
        assertThat(retried.deliveryState()).isEqualTo("accepted");
        assertThat(destination.createdOrders).hasSize(1);
        ExchangeReceipt beforeResults = exchange.report("mini-his", submission.externalRequestId());
        assertThat(beforeResults.observations()).isEmpty();
        assertThat(beforeResults.diagnosticReport().path("result")).isEmpty();
    }

    private static SourceRegistry registry() {
        InteropSourcesProperties properties = new InteropSourcesProperties();
        properties.getSources().put("mini-his", source("org-mini-his", "Mini HIS", "patient"));
        properties.getSources().put("mini-lis", source("org-mini-lis", "Mini LIS", "service-request"));
        properties.getSources().put("clinic-b", source("org-clinic-b", "Clinic B", "service-request"));
        return new SourceRegistry(properties);
    }

    private static InteropSourcesProperties.SourceProperties source(String organization, String name, String capability) {
        InteropSourcesProperties.SourceProperties properties = new InteropSourcesProperties.SourceProperties();
        properties.setOrganizationId(organization);
        properties.setDisplayName(name);
        properties.setBaseUrl("http://127.0.0.1:9");
        properties.setCapabilities(List.of(capability));
        return properties;
    }

    private static OrderSubmission submission(String patientId, String orderId, String givenName) {
        return submissionTo("mini-lis", patientId, orderId, givenName);
    }

    private static OrderSubmission submissionTo(String destination, String patientId, String orderId) {
        return submissionTo(destination, patientId, orderId, "Ana");
    }

    private static OrderSubmission submissionTo(String destination, String patientId, String orderId, String givenName) {
        return new OrderSubmission(
                "org-mini-his",
                destination,
                orderId,
                "GLU",
                "Glucose",
                OffsetDateTime.parse("2026-03-01T10:00:00Z"),
                new PatientIdentity(
                        "https://lab.local/mini-his/patient",
                        patientId,
                        "Quispe",
                        givenName,
                        LocalDate.parse("1984-03-12"),
                        "female"));
    }

    private static final class FakeDestination implements OrderDestination, ResultSource {
        private final List<String> patientLookups = new ArrayList<>();
        private final Map<String, String> patients = new LinkedHashMap<>();
        private final Map<String, String> alreadyStored = new LinkedHashMap<>();
        private final List<String> createdOrders = new ArrayList<>();
        private int orderPosts;
        private boolean failNext;

        @Override
        public String systemKey() {
            return "mini-lis";
        }

        @Override
        public String resolvePatient(String requestingOrganizationId, PatientIdentity identity) {
            String key = requestingOrganizationId + "|" + identity.identifierValue();
            patientLookups.add(key);
            return patients.computeIfAbsent(key, ignored -> "MLS-PAT-" + patients.size());
        }

        @Override
        public AcceptedOrder accept(DestinationCommand command) {
            orderPosts++;
            if (failNext) {
                failNext = false;
                throw ExchangeException.unavailable();
            }
            String key = command.requestingOrganizationId() + "|" + command.externalRequestId();
            String existing = alreadyStored.get(key);
            if (existing != null) {
                return new AcceptedOrder(existing, true);
            }
            String created = "MLS-ORD-" + (createdOrders.size() + 1);
            createdOrders.add(created);
            alreadyStored.put(key, created);
            return new AcceptedOrder(created, false);
        }

        @Override
        public DestinationReport read(String destinationOrderId) {
            com.fasterxml.jackson.databind.node.ObjectNode report = new ObjectMapper().createObjectNode();
            report.put("resourceType", "DiagnosticReport");
            report.putArray("result");
            return new DestinationReport(report, report, List.of());
        }
    }

    private static final class MemoryStore implements ExchangeStore {
        private final Map<String, String> links = new LinkedHashMap<>();
        private final Map<String, OrderCorrelation> orders = new LinkedHashMap<>();

        @Override
        public Optional<String> findPatientLink(
                String sourceSystem, String identifierSystem, String identifierValue, String destinationSystem) {
            return Optional.ofNullable(links.get(sourceSystem + "|" + identifierSystem + "|" + identifierValue + "|" + destinationSystem));
        }

        @Override
        public void savePatientLink(
                String sourceSystem,
                String identifierSystem,
                String identifierValue,
                String destinationSystem,
                String destinationPatientId) {
            links.putIfAbsent(
                    sourceSystem + "|" + identifierSystem + "|" + identifierValue + "|" + destinationSystem,
                    destinationPatientId);
        }

        @Override
        public Optional<OrderCorrelation> findOrder(
                String sourceSystem, String sourceOrganizationId, String sourceOrderId, String destinationSystem) {
            return Optional.ofNullable(orders.get(sourceSystem + "|" + sourceOrganizationId + "|" + sourceOrderId + "|" + destinationSystem));
        }

        @Override
        public Optional<OrderCorrelation> findOwnedOrder(String sourceSystem, String sourceOrderId) {
            List<OrderCorrelation> found = orders.values().stream()
                    .filter(order -> order.sourceSystem().equals(sourceSystem) && order.sourceOrderId().equals(sourceOrderId))
                    .toList();
            if (found.size() > 1) {
                throw ExchangeException.invalidRequest();
            }
            return found.stream().findFirst();
        }

        @Override
        public void insert(OrderCorrelation correlation) {
            orders.put(key(correlation), correlation);
        }

        @Override
        public void updateDelivery(
                String correlationId,
                String deliveryState,
                String errorCode,
                String destinationOrderId,
                String destinationPatientId) {
            OrderCorrelation current = orders.values().stream()
                    .filter(order -> order.correlationId().equals(correlationId))
                    .findFirst()
                    .orElseThrow();
            OrderCorrelation updated = new OrderCorrelation(
                    current.correlationId(),
                    current.sourceSystem(),
                    current.sourceOrganizationId(),
                    current.sourceOrderId(),
                    current.destinationSystem(),
                    current.destinationOrganizationId(),
                    destinationOrderId == null ? current.destinationOrderId() : destinationOrderId,
                    destinationPatientId == null ? current.destinationPatientId() : destinationPatientId,
                    current.patientIdentifierSystem(),
                    current.patientIdentifierValue(),
                    current.testCode(),
                    current.testDescription(),
                    current.requestedAt(),
                    deliveryState,
                    errorCode);
            orders.put(key(updated), updated);
        }

        private static String key(OrderCorrelation correlation) {
            return correlation.sourceSystem() + "|" + correlation.sourceOrganizationId() + "|"
                    + correlation.sourceOrderId() + "|" + correlation.destinationSystem();
        }

        @Override
        public Optional<OrderCorrelation> findByDestinationOrder(String destinationSystem, String destinationOrderId) {
            List<OrderCorrelation> found = orders.values().stream()
                    .filter(order -> destinationSystem.equals(order.destinationSystem())
                            && destinationOrderId.equals(order.destinationOrderId()))
                    .toList();
            if (found.size() > 1) {
                throw ExchangeException.invalidRequest();
            }
            return found.stream().findFirst();
        }

        @Override
        public boolean saveHl7Observation(
                String messageControlId,
                String destinationOrderId,
                String sourceOrderId,
                String externalResultId,
                String observationJson) {
            return false;
        }

        @Override
        public List<String> hl7Observations(String destinationOrderId) {
            return List.of();
        }
    }
}
