package lab.healthcare.minilis;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.time.LocalDate;
import java.time.OffsetDateTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@Testcontainers
@SpringBootTest
@AutoConfigureMockMvc
class CriticalLabBenchTest {

    @Container
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine");

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
        registry.add("mini-lis.service-token", () -> "lab-mini-lis-dev");
        registry.add("mini-lis.bench-password", () -> "bench-test-secret");
    }

    @Autowired
    private MockMvc mockMvc;
    @Autowired
    private LaboratoryRecordService records;
    @Autowired
    private BenchWorkflow workflow;

    @Test
    void draftDoesNotPublishAndValidationCreatesOneCriticalEvent() {
        LabOrder order = order("718-7", "Hemoglobina", "MHS-PAT-CRIT");
        assertThatThrownBy(() -> workflow.advance(order.orderId(), "draft", "6.2", "g/dL", "", false))
                .isInstanceOf(MiniLisException.class);
        workflow.advance(order.orderId(), "register", null, null, null, false);
        workflow.advance(order.orderId(), "receive", null, null, null, false);
        workflow.advance(order.orderId(), "process", null, null, null, false);
        workflow.advance(order.orderId(), "draft", "6.2", "g/dL", "operacion sintetica", false);
        assertThat(records.resultsForOrder(order.orderId())).isEmpty();
        assertThatThrownBy(() -> workflow.advance(order.orderId(), "validate", null, null, null, false))
                .extracting(ex -> ((MiniLisException) ex).code()).isEqualTo("unauthorized");
        workflow.advance(order.orderId(), "validate", null, null, null, true);
        assertThat(records.resultsForOrder(order.orderId())).isEmpty();
        workflow.advance(order.orderId(), "publish", null, null, null, true);
        workflow.advance(order.orderId(), "publish", null, null, null, true);
        assertThat(records.resultsForOrder(order.orderId())).hasSize(1);
        assertThat(workflow.criticalEvent(order.orderId())).isPresent();
        assertThat(workflow.criticalEvent(order.orderId()).orElseThrow().get("original_value")).isEqualTo("6.2");
        workflow.advance(order.orderId(), "correct", "6.4", null, null, true);
        assertThat(records.resultsForOrder(order.orderId())).hasSize(2);
        assertThat(workflow.criticalEvent(order.orderId()).orElseThrow().get("original_value")).isEqualTo("6.2");
        assertThat(workflow.criticalEvent(order.orderId()).orElseThrow().get("current_value")).isEqualTo("6.4");
    }

    @Test
    void glucoseNinetyDoesNotCreateACriticalEvent() {
        LabOrder order = order("GLU", "Glucosa", "MHS-PAT-GLU");
        workflow.advance(order.orderId(), "register", null, null, null, true);
        workflow.advance(order.orderId(), "receive", null, null, null, true);
        workflow.advance(order.orderId(), "process", null, null, null, true);
        workflow.advance(order.orderId(), "draft", "90", "mg/dL", "", true);
        workflow.advance(order.orderId(), "validate", null, null, null, true);
        workflow.advance(order.orderId(), "publish", null, null, null, true);
        assertThat(workflow.criticalEvent(order.orderId())).isEmpty();
        assertThat(CriticalRule.matches("718-7", "g/dL", "13.4")).isFalse();
        assertThat(CriticalRule.matches("718-7", "g/dL", "6.2")).isTrue();
    }

    @Test
    void benchPageUsesTheLaboratorySession() throws Exception {
        mockMvc.perform(get("/bench/orders")).andExpect(status().is3xxRedirection());
        var login = mockMvc.perform(post("/bench/login").param("username", "tecnico").param("password", "bench-test-secret"))
                .andExpect(status().is3xxRedirection())
                .andReturn();
        MockHttpSession session = (MockHttpSession) login.getRequest().getSession(false);
        mockMvc.perform(get("/bench/login")).andExpect(content().string(org.hamcrest.Matchers.containsString("No es OIDC")));
        mockMvc.perform(get("/bench/orders").session(session))
                .andExpect(status().isOk())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("Mini LIS")));
    }

    private LabOrder order(String testCode, String description, String externalPatient) {
        ExternalPatient patient = records.registerPatient(new NewPatient(
                "org-mini-his", externalPatient, "Quispe", "Ana", LocalDate.parse("1984-03-12"), "female"));
        return records.createOrder(new NewOrder(
                patient.patientId(), "org-mini-his", "HIS-" + externalPatient, testCode, description,
                OffsetDateTime.parse("2026-03-01T10:00:00Z")));
    }
}
