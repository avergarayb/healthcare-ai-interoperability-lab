package lab.healthcare.minihis;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class MiniHisLabOrderTest {

    private static final Path DATABASE = Path.of(System.getProperty("java.io.tmpdir"), "mini-his-lab-order-v1.sqlite");
    private static HttpServer exchange;
    private static final AtomicReference<String> submittedBody = new AtomicReference<>();

    @DynamicPropertySource
    static void exchangeStub(DynamicPropertyRegistry registry) throws Exception {
        Files.deleteIfExists(DATABASE);
        exchange = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        exchange.createContext("/api/exchange/v1/orders", http -> {
            String path = http.getRequestURI().getPath();
            byte[] body;
            if (path.endsWith("/report")) {
                body = """
                        {"correlationId":"EXC-TEST","deliveryState":"accepted","observations":[{"resourceType":"Observation","valueQuantity":{"value":141,"unit":"mmol/L"}}]}
                        """.getBytes(StandardCharsets.UTF_8);
            } else {
                submittedBody.set(new String(http.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
                body = """
                        {"correlationId":"EXC-TEST","deliveryState":"accepted","destination":{"systemKey":"mini-lis","organizationId":"org-mini-lis","orderId":"MLS-ORD-TEST"}}
                        """.getBytes(StandardCharsets.UTF_8);
            }
            http.sendResponseHeaders(200, body.length);
            http.getResponseBody().write(body);
            http.close();
        });
        exchange.start();
        registry.add("mini-his.sqlite-path", DATABASE::toString);
        registry.add("mini-his.exchange.base-url", () -> "http://127.0.0.1:" + exchange.getAddress().getPort());
        registry.add("mini-his.exchange.service-token", () -> "his-stub-token");
    }

    @AfterAll
    static void stop() {
        if (exchange != null) {
            exchange.stop(0);
        }
    }

    @Autowired
    private MockMvc mockMvc;

    @Test
    void submissionGoesToTheExchangeAndNotToALaboratoryUrl() throws Exception {
        String created = mockMvc.perform(post("/lab-orders")
                        .contentType("application/json")
                        .content("""
                                {"patientId":"MHS-PAT-001","destinationSystemKey":"mini-lis","testCode":"GLU","testDescription":"Glucose","requestedAt":"2026-03-01T10:00:00Z"}
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.localStatus").value("recorded"))
                .andReturn()
                .getResponse()
                .getContentAsString();
        String orderId = created.replaceAll(".*\"orderId\":\"([^\"]+)\".*", "$1");
        mockMvc.perform(get("/patients/MHS-PAT-001/lab-orders"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].orderId").value(orderId))
                .andExpect(jsonPath("$[0].localStatus").value("recorded"));
        mockMvc.perform(post("/lab-orders/" + orderId + "/submission"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.correlationId").value("EXC-TEST"));
        assertThat(submittedBody.get()).contains("org-mini-his").contains("MHS-PAT-001");
        assertThat(submittedBody.get()).doesNotContain("8096").doesNotContain("/orders");
        mockMvc.perform(get("/patients/MHS-PAT-002/lab-orders"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(0));
        mockMvc.perform(get("/patients/UNKNOWN/lab-orders"))
                .andExpect(status().isNotFound());
        mockMvc.perform(get("/lab-orders/" + orderId + "/results"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.observations[0].valueQuantity.value").value(141));
    }
}
