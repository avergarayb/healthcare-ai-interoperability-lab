package lab.healthcare.minihis;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class HospitalSecurityTest {
    private static final Path DATABASE = Path.of(System.getProperty("java.io.tmpdir"), "mini-his-hospital-security.sqlite");

    @Autowired
    private MockMvc mvc;
    @Autowired
    private JdbcTemplate jdbc;

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) throws Exception {
        Files.deleteIfExists(DATABASE);
        registry.add("mini-his.sqlite-path", DATABASE::toString);
        registry.add("mini-his.inpatient.ward-password", () -> "ward-test-secret");
        registry.add("mini-his.oidc.enabled", () -> "true");
        registry.add("mini-his.oidc.client-enabled", () -> "false");
    }

    @Test
    void anonymousExpiredAndLocalPasswordDoNotEnter() throws Exception {
        mvc.perform(get("/ward/patients")).andExpect(status().is3xxRedirection());
        mvc.perform(get("/showcase")).andExpect(status().is3xxRedirection());
        var login = mvc.perform(post("/ward/login").param("username", "clinica").param("password", "ward-test-secret"))
                .andExpect(redirectedUrl("/ward/login?aviso=use-oidc"))
                .andReturn();
        assertThat(login.getRequest().getSession(false) == null
                || login.getRequest().getSession(false).getAttribute("wardPrincipal") == null).isTrue();
        String page = mvc.perform(get("/ward/login")).andReturn().getResponse().getContentAsString();
        assertThat(page).contains("proveedor OIDC").doesNotContain("ward-test-secret");
    }

    @Test
    void auditorAndForeignOrganizationCannotMutateOrRead() throws Exception {
        int before = jdbc.queryForObject("select count(*) from lab_order", Integer.class);
        mvc.perform(post("/ward/orders").session(session("auditor.his", "auditor", "org-mini-his"))
                        .param("csrf", "csrf-test").param("patientId", "MHS-PAT-001").param("testCode", "718-7")
                        .param("indication", "sintetica").param("requestedOn", "2026-11-19"))
                .andExpect(status().is3xxRedirection());
        mvc.perform(post("/ward/orders").session(session("medico.his", "clinician", "org-mini-his"))
                        .param("patientId", "MHS-PAT-001").param("testCode", "718-7")
                        .param("indication", "sintetica").param("requestedOn", "2026-11-19"))
                .andExpect(status().is3xxRedirection());
        assertThat(jdbc.queryForObject("select count(*) from lab_order", Integer.class)).isEqualTo(before);
        mvc.perform(post("/showcase/demo-001/case/sum-aaaaaaaaaaaa/decision")
                        .session(session("medico.his", "clinician", "org-mini-his"))
                        .param("csrf", "csrf-test").param("decision", "approved"))
                .andExpect(redirectedUrl("/ward/login?aviso=no-autorizado"));
        String foreign = mvc.perform(get("/ward/patients/MHS-PAT-001")
                        .session(session("reviewer-pe", "clinician", "org-pe-lab-demo")))
                .andExpect(status().is3xxRedirection())
                .andReturn().getResponse().getContentAsString();
        assertThat(foreign).doesNotContain("Quispe");
        String own = mvc.perform(get("/ward/patients/MHS-PAT-001")
                        .session(session("medico.his", "clinician", "org-mini-his")))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        assertThat(own).contains("Sesión OIDC").contains("MHS-PAT-001");
    }

    @Test
    void logoutInvalidatesTheSessionAndABadCsrfDoesNot() throws Exception {
        MockHttpSession session = session("medico.his", "clinician", "org-mini-his");
        mvc.perform(post("/ward/logout").session(session)).andExpect(redirectedUrl("/ward/patients"));
        mvc.perform(get("/ward/patients").session(session)).andExpect(status().isOk());
        mvc.perform(post("/ward/logout").session(session).param("csrf", "csrf-test"))
                .andExpect(redirectedUrl("/ward/login"));
        mvc.perform(get("/ward/patients").session(session)).andExpect(status().is3xxRedirection());
        mvc.perform(get("/ward/orders/MHS-LAB-FOREIGN").session(session("medico.his", "clinician", "org-es-lab-demo")))
                .andExpect(status().is3xxRedirection());
        mvc.perform(get("/ward/episodes/ENC-FOREIGN").session(session("medico.his", "clinician", "org-es-lab-demo")))
                .andExpect(status().is3xxRedirection());
    }

    private static MockHttpSession session(String user, String role, String organization) {
        MockHttpSession session = new MockHttpSession();
        session.setAttribute("wardPrincipal", new WardPrincipal(user, role, organization, "oidc"));
        session.setAttribute("csrf", "csrf-test");
        return session;
    }
}
