package lab.healthcare.minihis;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrlPattern;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class WardLabOrderTest {

    private static final Path DATABASE = Path.of(System.getProperty("java.io.tmpdir"), "mini-his-health-004.sqlite");

    @Autowired
    private MockMvc mvc;
    @Autowired
    private LabOrderStore orders;

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) throws Exception {
        Files.deleteIfExists(DATABASE);
        registry.add("mini-his.sqlite-path", DATABASE::toString);
        registry.add("mini-his.inpatient.ward-password", () -> "ward-test-secret");
    }

    @Test
    void clinicianSeesAFailedSendAndAnAuditorCannotCreateAnOrder() throws Exception {
        assertThat(CriticalHemoglobinRule.matches("718-7", "g/dL", "13.4")).isFalse();
        assertThat(CriticalHemoglobinRule.matches("718-7", "g/dL", "6.2")).isTrue();
        assertThat(CriticalHemoglobinRule.matches("GLU", "mg/dL", "90")).isFalse();
        MockHttpSession session = login("clinica");
        String csrf = String.valueOf(session.getAttribute("csrf"));
        MvcResult created = mvc.perform(post("/ward/orders").session(session)
                        .param("csrf", csrf)
                        .param("patientId", "MHS-PAT-001")
                        .param("testCode", "718-7")
                        .param("indication", "Control sintetico")
                        .param("requestedOn", "2026-11-18"))
                .andExpect(status().is3xxRedirection())
                .andExpect(redirectedUrlPattern("/ward/orders/*"))
                .andReturn();
        String location = created.getResponse().getRedirectedUrl();
        mvc.perform(get(location).session(session))
                .andExpect(status().isOk())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("No enviada")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("Hemoglobina")));
        assertThat(orders.listAll()).hasSize(1);
        assertThat(orders.listAll().get(0).localStatus()).isEqualTo("failed");
        MockHttpSession auditor = login("auditor");
        mvc.perform(post("/ward/orders").session(auditor)
                        .param("csrf", String.valueOf(auditor.getAttribute("csrf")))
                        .param("patientId", "MHS-PAT-001")
                        .param("testCode", "718-7")
                        .param("indication", "No autorizado")
                        .param("requestedOn", "2026-11-18"))
                .andExpect(status().is3xxRedirection());
        assertThat(orders.listAll()).hasSize(1);
    }

    private MockHttpSession login(String username) throws Exception {
        MvcResult result = mvc.perform(post("/ward/login").param("username", username).param("password", "ward-test-secret"))
                .andExpect(status().is3xxRedirection())
                .andReturn();
        return (MockHttpSession) result.getRequest().getSession(false);
    }
}
