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
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class ShowcasePortalTest {

    private static final Path DATABASE = Path.of(System.getProperty("java.io.tmpdir"), "mini-his-showcase.sqlite");

    @Autowired
    private MockMvc mvc;
    @Autowired
    private InpatientStore store;

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) throws Exception {
        Files.deleteIfExists(DATABASE);
        registry.add("mini-his.sqlite-path", DATABASE::toString);
        registry.add("mini-his.inpatient.ward-password", () -> "ward-test-secret");
        registry.add("showcase.lis-health", () -> "http://127.0.0.1:1/health");
        registry.add("showcase.fhir-health", () -> "http://127.0.0.1:1/health");
        registry.add("showcase.ai-health", () -> "http://127.0.0.1:1/health");
        registry.add("showcase.longitudinal-health", () -> "");
        registry.add("showcase.lis-bench", () -> "http://127.0.0.1:1/bench/orders");
    }

    @Test
    void catalogStatesTheRealAvailabilityAndDoesNotClaimReady() throws Exception {
        assertThat(ShowcaseProbe.allowed("http://example.com/health")).isFalse();
        assertThat(ShowcaseProbe.allowed("http://127.0.0.1:9/health")).isTrue();
        mvc.perform(get("/showcase"))
                .andExpect(status().isOk())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("Resumen de laboratorio")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("Comparación longitudinal")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("Interoperabilidad HL7/FHIR")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("Resultado crítico")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("Preparación de alta")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("No disponible")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("Perfil aislado")))
                .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("READY"))));
        mvc.perform(get("/showcase/demo-002"))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("no es el OIDC")));
        mvc.perform(get("/showcase/demo-004"))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("Pendiente")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("Consultar en Mini LIS")))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("/ward/orders/new")));
        mvc.perform(get("/showcase/demo-003"))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("Verificar en Federación")));
        mvc.perform(get("/showcase/demo-001"))
                .andExpect(content().string(org.hamcrest.Matchers.containsString("/showcase/demo-001/case")));
    }

    @Test
    void twoEpisodesStayIndependentAndAnAuditorCannotPrepareOne() throws Exception {
        int before = store.episodes().size();
        MockHttpSession clinician = login("clinica");
        String first = prepare(clinician);
        String second = prepare(clinician);
        assertThat(first).isNotEqualTo(second);
        assertThat(store.episodes()).hasSize(before + 2);
        MockHttpSession auditor = login("auditor");
        mvc.perform(post("/ward/showcase/episode").session(auditor)
                        .param("csrf", String.valueOf(auditor.getAttribute("csrf"))))
                .andExpect(status().is3xxRedirection());
        assertThat(store.episodes()).hasSize(before + 2);
        mvc.perform(post("/showcase/demo-001/case").session(auditor)
                        .param("csrf", String.valueOf(auditor.getAttribute("csrf"))))
                .andExpect(status().is3xxRedirection())
                .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl("/ward/login?aviso=no-autorizado"));
        MockHttpSession clinicianAgain = login("clinica");
        mvc.perform(post("/showcase/demo-001/case").session(clinicianAgain)
                        .param("csrf", String.valueOf(clinicianAgain.getAttribute("csrf"))))
                .andExpect(status().is3xxRedirection())
                .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrlPattern("/showcase/demo-001/case?aviso=*"));
    }

    private String prepare(MockHttpSession session) throws Exception {
        MvcResult result = mvc.perform(post("/ward/showcase/episode").session(session)
                        .param("csrf", String.valueOf(session.getAttribute("csrf"))))
                .andExpect(status().is3xxRedirection())
                .andReturn();
        String location = result.getResponse().getRedirectedUrl();
        return location.substring(location.lastIndexOf('/') + 1);
    }

    private MockHttpSession login(String username) throws Exception {
        MvcResult result = mvc.perform(post("/ward/login").param("username", username).param("password", "ward-test-secret"))
                .andExpect(status().is3xxRedirection())
                .andReturn();
        return (MockHttpSession) result.getRequest().getSession(false);
    }
}
