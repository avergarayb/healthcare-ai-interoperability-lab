package lab.healthcare.minilis;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@Testcontainers
@SpringBootTest
@AutoConfigureMockMvc
class MiniLisApiTest {

    private static final String TOKEN = "lab-mini-lis-dev";

    @Container
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine");

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
        registry.add("mini-lis.service-token", () -> TOKEN);
    }

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private LaboratoryRecordService records;

    @Test
    void healthDoesNotRequireTheServiceToken() throws Exception {
        mockMvc.perform(get("/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("up"));
    }

    @Test
    void clinicalRoutesRejectAMissingToken() throws Exception {
        mockMvc.perform(get("/patients"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void seedCoversPendingFinalAndMultipleResults() throws Exception {
        mockMvc.perform(get("/orders/MLS-ORD-001").header("X-Service-Token", TOKEN))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ORDERED"))
                .andExpect(jsonPath("$.patientId").value("MLS-PAT-001"))
                .andExpect(jsonPath("$.requestingOrganizationId").value("org-mini-his"));
        mockMvc.perform(get("/orders/MLS-ORD-001/results").header("X-Service-Token", TOKEN))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(0)));

        mockMvc.perform(get("/orders/MLS-ORD-002").header("X-Service-Token", TOKEN))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("COMPLETED"));
        mockMvc.perform(get("/orders/MLS-ORD-002/results").header("X-Service-Token", TOKEN))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].status").value("FINAL"))
                .andExpect(jsonPath("$[0].value").value("13.5"))
                .andExpect(jsonPath("$[0].unit").value("g/dL"));

        mockMvc.perform(get("/patients/MLS-PAT-003/results").header("X-Service-Token", TOKEN))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(2)));

        int before = records.storedPatients();
        records.storedPatients();
        assert before == records.storedPatients();
    }

    @Test
    void registersAPatientOrderAndResultAndKeepsThem() throws Exception {
        String patientBody = """
                {"organizationId":"org-mini-lis","externalId":"EXT-PAT-900","familyName":"Salazar","givenName":"Ines","birthDate":"1988-04-04","administrativeSex":"female"}
                """;
        String patientId = mockMvc.perform(post("/patients")
                        .header("X-Service-Token", TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(patientBody))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.patientId").exists())
                .andReturn()
                .getResponse()
                .getContentAsString();
        String id = patientId.replaceAll(".*\"patientId\":\"([^\"]+)\".*", "$1");

        mockMvc.perform(get("/patients").param("organizationId", "org-mini-lis").param("externalId", "EXT-PAT-900")
                        .header("X-Service-Token", TOKEN))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].patientId").value(id));

        String orderBody = """
                {"patientId":"%s","requestingOrganizationId":"org-mini-his","externalRequestId":"EXT-REQ-900","testCode":"NA","testDescription":"Sodium","requestedAt":"2026-03-01T10:00:00Z"}
                """.formatted(id);
        String orderJson = mockMvc.perform(post("/orders")
                        .header("X-Service-Token", TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(orderBody))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("ORDERED"))
                .andReturn()
                .getResponse()
                .getContentAsString();
        String orderId = orderJson.replaceAll(".*\"orderId\":\"([^\"]+)\".*", "$1");

        mockMvc.perform(get("/orders/" + orderId).header("X-Service-Token", TOKEN))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.patientId").value(id));

        String resultBody = """
                {"externalResultId":"EXT-RES-900","testCode":"NA","value":"140","unit":"mmol/L","referenceRange":"135-145","resultedAt":"2026-03-01T12:00:00Z","status":"FINAL"}
                """;
        mockMvc.perform(post("/orders/" + orderId + "/results")
                        .header("X-Service-Token", TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(resultBody))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("FINAL"));

        mockMvc.perform(get("/orders/" + orderId).header("X-Service-Token", TOKEN))
                .andExpect(jsonPath("$.status").value("IN_PROGRESS"));
        mockMvc.perform(post("/orders/" + orderId + "/completion").header("X-Service-Token", TOKEN))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("COMPLETED"));
        mockMvc.perform(get("/patients/" + id + "/results").header("X-Service-Token", TOKEN))
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].value").value("140"));
    }

    @Test
    void duplicateExternalIdentityIsRejected() throws Exception {
        String body = """
                {"organizationId":"org-mini-lis","externalId":"EXT-PAT-901","familyName":"Nunez","givenName":"Oscar","birthDate":"1970-01-01","administrativeSex":"male"}
                """;
        mockMvc.perform(post("/patients").header("X-Service-Token", TOKEN).contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isCreated());
        mockMvc.perform(post("/patients").header("X-Service-Token", TOKEN).contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.error").value("duplicate"));

        String patientId = records.searchPatients("org-mini-lis", "EXT-PAT-901").get(0).patientId();
        String order = """
                {"patientId":"%s","requestingOrganizationId":"org-mini-his","externalRequestId":"EXT-REQ-901","testCode":"K","testDescription":"Potassium","requestedAt":"2026-03-02T10:00:00Z"}
                """.formatted(patientId);
        mockMvc.perform(post("/orders").header("X-Service-Token", TOKEN).contentType(MediaType.APPLICATION_JSON).content(order))
                .andExpect(status().isCreated());
        mockMvc.perform(post("/orders").header("X-Service-Token", TOKEN).contentType(MediaType.APPLICATION_JSON).content(order))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.error").value("duplicate"));
    }

    @Test
    void missingOrderAndInvalidResultFail() throws Exception {
        mockMvc.perform(get("/orders/MLS-ORD-MISSING").header("X-Service-Token", TOKEN))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("not_found"));

        String result = """
                {"externalResultId":"EXT-RES-MISSING","testCode":"GLU","value":"","unit":"mg/dL","resultedAt":"2026-03-01T12:00:00Z","status":"FINAL"}
                """;
        mockMvc.perform(post("/orders/MLS-ORD-001/results")
                        .header("X-Service-Token", TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(result))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_request"));

        mockMvc.perform(post("/orders/MLS-ORD-002/results")
                        .header("X-Service-Token", TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"externalResultId":"EXT-RES-LATE","testCode":"HGB","value":"11","unit":"g/dL","resultedAt":"2026-02-03T12:00:00Z","status":"FINAL"}
                                """))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.error").value("invalid_transition"));
    }

    @Test
    void cancellationIsRejectedAfterAFinalResult() throws Exception {
        mockMvc.perform(post("/orders/MLS-ORD-002/cancellation").header("X-Service-Token", TOKEN))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.error").value("invalid_transition"));

        String patientBody = """
                {"organizationId":"org-mini-lis","externalId":"EXT-PAT-902","familyName":"Vega","givenName":"Rita","birthDate":"1992-08-08","administrativeSex":"female"}
                """;
        String created = mockMvc.perform(post("/patients")
                        .header("X-Service-Token", TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(patientBody))
                .andExpect(status().isCreated())
                .andReturn()
                .getResponse()
                .getContentAsString();
        String patientId = created.replaceAll(".*\"patientId\":\"([^\"]+)\".*", "$1");
        String orderBody = """
                {"patientId":"%s","requestingOrganizationId":"org-mini-his","externalRequestId":"EXT-REQ-902","testCode":"GLU","testDescription":"Glucose","requestedAt":"2026-04-01T10:00:00Z"}
                """.formatted(patientId);
        String orderJson = mockMvc.perform(post("/orders")
                        .header("X-Service-Token", TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(orderBody))
                .andExpect(status().isCreated())
                .andReturn()
                .getResponse()
                .getContentAsString();
        String orderId = orderJson.replaceAll(".*\"orderId\":\"([^\"]+)\".*", "$1");
        mockMvc.perform(post("/orders/" + orderId + "/cancellation").header("X-Service-Token", TOKEN))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("CANCELLED"));
        mockMvc.perform(post("/orders/" + orderId + "/results")
                        .header("X-Service-Token", TOKEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"externalResultId":"EXT-RES-902","testCode":"GLU","value":"100","unit":"mg/dL","resultedAt":"2026-04-01T12:00:00Z","status":"FINAL"}
                                """))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.error").value("invalid_transition"));
    }

    @Test
    void externalRequestLookupReturnsTheStoredOrder() throws Exception {
        mockMvc.perform(get("/orders")
                        .header("X-Service-Token", TOKEN)
                        .param("requestingOrganizationId", "org-mini-his")
                        .param("externalRequestId", "EXT-REQ-001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.orderId").value("MLS-ORD-001"));
        mockMvc.perform(get("/orders")
                        .header("X-Service-Token", TOKEN)
                        .param("externalRequestId", "EXT-REQ-001"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_request"));
    }
}
