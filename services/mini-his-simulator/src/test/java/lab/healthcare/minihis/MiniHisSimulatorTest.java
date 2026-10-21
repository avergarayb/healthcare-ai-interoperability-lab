package lab.healthcare.minihis;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class MiniHisSimulatorTest {

    private static final Path DATABASE = Path.of(System.getProperty("java.io.tmpdir"), "mini-his-simulator-v1.sqlite");

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) throws Exception {
        Files.deleteIfExists(DATABASE);
        registry.add("mini-his.sqlite-path", DATABASE::toString);
    }

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private MiniHisStore store;

    @Autowired
    private JdbcTemplate jdbc;

    @Test
    void startsAloneAndServesTheSyntheticSeed() throws Exception {
        store.ensureReady();

        mockMvc.perform(get("/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("up"));

        mockMvc.perform(get("/patients"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(6))
                .andExpect(jsonPath("$[0].patientId").value("MHS-PAT-001"))
                .andExpect(jsonPath("$[0].familyName").value("Quispe"))
                .andExpect(jsonPath("$[0].givenName").value("Ana"))
                .andExpect(jsonPath("$[0].birthDate").value("1984-03-12"))
                .andExpect(jsonPath("$[0].administrativeSex").value("female"))
                .andExpect(jsonPath("$[1].patientId").value("MHS-PAT-002"))
                .andExpect(jsonPath("$[2].patientId").value("MHS-PAT-003"));

        mockMvc.perform(get("/patients").param("limit", "1"))
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].patientId").value("MHS-PAT-001"));

        SeedCounts before = store.counts();
        store.ensureReady();
        assertThat(store.counts()).isEqualTo(before);
        assertThat(store.foreignKeysEnabled()).isTrue();
    }

    @Test
    void consultationsAndResultsStayRelatedAndOrdered() throws Exception {
        mockMvc.perform(get("/patients/MHS-PAT-001/consultations"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].consultationId").value("MHS-CON-001"))
                .andExpect(jsonPath("$[0].patientId").value("MHS-PAT-001"))
                .andExpect(jsonPath("$[0].status").value("completed"))
                .andExpect(jsonPath("$[0].careClass").value("ambulatory"))
                .andExpect(jsonPath("$[0].occurredAt").value("2026-09-01T15:00:00Z"));

        mockMvc.perform(get("/consultations/MHS-CON-001/results"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].resultId").value("MHS-RES-001"))
                .andExpect(jsonPath("$[0].consultationId").value("MHS-CON-001"))
                .andExpect(jsonPath("$[0].patientId").value("MHS-PAT-001"))
                .andExpect(jsonPath("$[0].status").value("final"))
                .andExpect(jsonPath("$[1].resultId").value("MHS-RES-002"))
                .andExpect(jsonPath("$[1].status").value("final"));

        mockMvc.perform(get("/patients/MHS-PAT-001/results"))
                .andExpect(jsonPath("$[0].resultId").value("MHS-RES-001"))
                .andExpect(jsonPath("$[1].resultId").value("MHS-RES-002"));

        Integer orphans = jdbc.queryForObject(
                """
                SELECT COUNT(*) FROM clinical_result result
                WHERE NOT EXISTS (
                    SELECT 1 FROM consultation visit
                    WHERE visit.consultation_id = result.consultation_id
                      AND visit.patient_id = result.patient_id
                )
                """,
                Integer.class);
        assertThat(orphans).isZero();
        assertThatThrownBy(() -> jdbc.update(
                """
                INSERT INTO clinical_result (
                    result_id, consultation_id, patient_id, result_type, display_name,
                    value_text, unit, observed_at
                ) VALUES ('MHS-RES-999', 'MHS-CON-001', 'MHS-PAT-002', 'laboratory', 'X', '1', '', '2026-09-01T15:30:00Z')
                """))
                .isInstanceOf(DataAccessException.class);

        Integer historicalAppointments = jdbc.queryForObject(
                """
                SELECT COUNT(*) FROM appointment
                WHERE patient_id IN ('MHS-PAT-001', 'MHS-PAT-002', 'MHS-PAT-003')
                """,
                Integer.class);
        assertThat(historicalAppointments).isZero();
    }

    @Test
    void unknownIdsReturnNotFoundWithoutFhirPayload() throws Exception {
        String body = mockMvc.perform(get("/patients/MHS-PAT-999"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("not_found"))
                .andReturn()
                .getResponse()
                .getContentAsString();
        assertThat(body).doesNotContain("resourceType").doesNotContain("Bundle").doesNotContain("Patient/");

        mockMvc.perform(get("/patients/missing/consultations")).andExpect(status().isNotFound());
        mockMvc.perform(get("/consultations/missing")).andExpect(status().isNotFound());
        mockMvc.perform(get("/consultations/missing/results")).andExpect(status().isNotFound());
        mockMvc.perform(get("/results/MHS-RES-999"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("not_found"));
        mockMvc.perform(get("/patients").param("limit", "101")).andExpect(status().isBadRequest());
    }

    @Test
    void resultSearchFiltersInTheDatabaseAndReportsTruncation() throws Exception {
        mockMvc.perform(get("/results").param("patientId", "MHS-PAT-404").param("status", "final"))
                .andExpect(status().isOk())
                .andExpect(header().string("X-More-Results", "false"))
                .andExpect(jsonPath("$.length()").value(0));
        mockMvc.perform(get("/results").param("patientId", "MHS-PAT-001").param("status", "preliminary"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(0));
        mockMvc.perform(get("/results").param("patientId", "MHS-PAT-001").param("status", "final").param("limit", "1"))
                .andExpect(status().isOk())
                .andExpect(header().string("X-More-Results", "true"))
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].resultId").value("MHS-RES-001"));

        mockMvc.perform(get("/results")).andExpect(status().isBadRequest()).andExpect(jsonPath("$.error").value("invalid_request"));
        mockMvc.perform(get("/results").param("patientId", " ")).andExpect(jsonPath("$.error").value("invalid_request"));
        mockMvc.perform(get("/results").param("patientId", "MHS-PAT-001").param("status", "final status"))
                .andExpect(jsonPath("$.error").value("invalid_request"));
        mockMvc.perform(get("/results").param("patientId", "MHS-PAT-001").param("limit", "0"))
                .andExpect(jsonPath("$.error").value("invalid_limit"));

        jdbc.execute("ALTER TABLE clinical_result RENAME TO clinical_result_hidden");
        try {
            mockMvc.perform(get("/results").param("patientId", "MHS-PAT-001"))
                    .andExpect(status().isServiceUnavailable())
                    .andExpect(jsonPath("$.error").value("unavailable"));
        } finally {
            jdbc.execute("ALTER TABLE clinical_result_hidden RENAME TO clinical_result");
        }
        mockMvc.perform(get("/results/MHS-RES-001")).andExpect(status().isOk());
    }

    @Test
    void resetRestoresTheStableSeedAndRejectsRemoteCallers() throws Exception {
        jdbc.update("DELETE FROM clinical_result WHERE consultation_id = 'MHS-CON-003'");
        jdbc.update("DELETE FROM consultation WHERE consultation_id = 'MHS-CON-003'");
        jdbc.update("DELETE FROM patient WHERE patient_id = 'MHS-PAT-003'");

        mockMvc.perform(post("/synthetic/reset").with(request -> {
                    request.setRemoteAddr("203.0.113.8");
                    return request;
                }))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.error").value("reset_not_local"));
        assertThat(store.findPatient("MHS-PAT-003")).isEmpty();

        mockMvc.perform(post("/synthetic/reset"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.patients").value(6))
                .andExpect(jsonPath("$.consultations").value(4))
                .andExpect(jsonPath("$.results").value(7));
        mockMvc.perform(get("/patients/MHS-PAT-003"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.patientId").value("MHS-PAT-003"));
        mockMvc.perform(get("/consultations/MHS-CON-003/results"))
                .andExpect(jsonPath("$[0].resultId").value("MHS-RES-005"))
                .andExpect(jsonPath("$[1].resultId").value("MHS-RES-006"));
        mockMvc.perform(get("/results").param("patientId", "MHS-PAT-001").param("status", "final"))
                .andExpect(status().isOk())
                .andExpect(header().string("X-More-Results", "false"))
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].resultId").value("MHS-RES-001"))
                .andExpect(jsonPath("$[0].patientId").value("MHS-PAT-001"))
                .andExpect(jsonPath("$[0].consultationId").value("MHS-CON-001"))
                .andExpect(jsonPath("$[0].valueText").value("13.4"))
                .andExpect(jsonPath("$[0].components.length()").value(0))
                .andExpect(jsonPath("$[1].resultId").value("MHS-RES-002"))
                .andExpect(jsonPath("$[1].valueText").value("120/80"))
                .andExpect(jsonPath("$[1].components.length()").value(2))
                .andExpect(jsonPath("$[1].components[0].componentId").value("MHS-CMP-002-1"))
                .andExpect(jsonPath("$[1].components[0].name").value("Presion sistolica"))
                .andExpect(jsonPath("$[1].components[0].valueDecimal").value("120"))
                .andExpect(jsonPath("$[1].components[0].unit").value("mmHg"))
                .andExpect(jsonPath("$[1].components[1].name").value("Presion diastolica"))
                .andExpect(jsonPath("$[1].components[1].valueDecimal").value("80"))
                .andExpect(jsonPath("$[1].components[1].unit").value("mmHg"));
        mockMvc.perform(get("/results").param("patientId", "MHS-PAT-002").param("status", "final"))
                .andExpect(jsonPath("$[0].resultId").value("MHS-RES-003"))
                .andExpect(jsonPath("$[?(@.patientId != 'MHS-PAT-002')]").doesNotExist());

        mockMvc.perform(get("/results/MHS-RES-002"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.valueText").value("120/80"))
                .andExpect(jsonPath("$.components.length()").value(2))
                .andExpect(jsonPath("$.components[0].valueDecimal").value("120"))
                .andExpect(jsonPath("$.components[1].valueDecimal").value("80"));
        mockMvc.perform(get("/results/MHS-RES-001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.resultId").value("MHS-RES-001"))
                .andExpect(jsonPath("$.consultationId").value("MHS-CON-001"))
                .andExpect(jsonPath("$.patientId").value("MHS-PAT-001"))
                .andExpect(jsonPath("$.status").value("final"))
                .andExpect(jsonPath("$.resourceType").doesNotExist());
    }

    @Test
    void followUpCaseSearchResolvesBoundPatients() throws Exception {
        mockMvc.perform(get("/patients")
                        .param("system", SyntheticSeed.FOLLOW_UP_CASE_SYSTEM)
                        .param("value", "SYN-FOLLOWUP-013"))
                .andExpect(status().isOk())
                .andExpect(header().string("X-More-Results", "false"))
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].patientId").value("MHS-PAT-004"))
                .andExpect(jsonPath("$[0].identifiers[0].system").value(SyntheticSeed.FOLLOW_UP_CASE_SYSTEM))
                .andExpect(jsonPath("$[0].identifiers[0].value").value("SYN-FOLLOWUP-013"));
        mockMvc.perform(get("/patients")
                        .param("system", SyntheticSeed.FOLLOW_UP_CASE_SYSTEM)
                        .param("value", "SYN-FOLLOWUP-014"))
                .andExpect(jsonPath("$[0].patientId").value("MHS-PAT-005"));
        mockMvc.perform(get("/patients")
                        .param("system", SyntheticSeed.FOLLOW_UP_CASE_SYSTEM)
                        .param("value", "SYN-FOLLOWUP-015"))
                .andExpect(jsonPath("$[0].patientId").value("MHS-PAT-006"));
        mockMvc.perform(get("/patients/MHS-PAT-006/consultations"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].consultationId").value("MHS-CON-015"))
                .andExpect(jsonPath("$[0].status").value("completed"));
        mockMvc.perform(get("/appointments").param("patientId", "MHS-PAT-006"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(0));
        mockMvc.perform(get("/patients")
                        .param("system", SyntheticSeed.PROPRIETARY_PATIENT_SYSTEM)
                        .param("value", "MHS-PAT-001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].patientId").value("MHS-PAT-001"))
                .andExpect(jsonPath("$[0].identifiers.length()").value(0));
        mockMvc.perform(get("/patients")
                        .param("system", SyntheticSeed.FOLLOW_UP_CASE_SYSTEM)
                        .param("value", "SYN-FOLLOWUP-404"))
                .andExpect(status().isOk())
                .andExpect(header().string("X-More-Results", "false"))
                .andExpect(jsonPath("$.length()").value(0));
        mockMvc.perform(get("/patients").param("system", SyntheticSeed.FOLLOW_UP_CASE_SYSTEM))
                .andExpect(status().isBadRequest());
    }

    @Test
    void appointmentsStayPastOrFutureWithoutRewritingStoredOffsets() throws Exception {
        String past = AppointmentStart.atOffset(AppointmentStart.PAST_OFFSET_DAYS, Clock.systemUTC());
        String future = AppointmentStart.atOffset(AppointmentStart.FUTURE_OFFSET_DAYS, Clock.systemUTC());

        mockMvc.perform(get("/appointments").param("patientId", "MHS-PAT-004"))
                .andExpect(status().isOk())
                .andExpect(header().string("X-More-Results", "false"))
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].appointmentId").value("MHS-APT-001"))
                .andExpect(jsonPath("$[0].patientId").value("MHS-PAT-004"))
                .andExpect(jsonPath("$[0].status").value("not_attended"))
                .andExpect(jsonPath("$[0].start").value(past));
        mockMvc.perform(get("/appointments").param("patientId", "MHS-PAT-005"))
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].appointmentId").value("MHS-APT-003"))
                .andExpect(jsonPath("$[0].status").value("not_attended"))
                .andExpect(jsonPath("$[0].start").value(past))
                .andExpect(jsonPath("$[1].appointmentId").value("MHS-APT-002"))
                .andExpect(jsonPath("$[1].status").value("confirmed"))
                .andExpect(jsonPath("$[1].start").value(future));
        mockMvc.perform(get("/appointments").param("patientId", "MHS-PAT-005").param("limit", "1"))
                .andExpect(header().string("X-More-Results", "true"))
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].appointmentId").value("MHS-APT-003"));
        mockMvc.perform(get("/appointments").param("patientId", "MHS-PAT-001"))
                .andExpect(status().isOk())
                .andExpect(header().string("X-More-Results", "false"))
                .andExpect(jsonPath("$.length()").value(0));
        mockMvc.perform(get("/appointments/MHS-APT-001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("not_attended"))
                .andExpect(jsonPath("$.start").value(past))
                .andExpect(jsonPath("$.resourceType").doesNotExist());
        mockMvc.perform(get("/appointments/MHS-APT-404"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("not_found"));
        mockMvc.perform(get("/appointments"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("invalid_request"));

        Integer historical = jdbc.queryForObject(
                """
                SELECT COUNT(*) FROM appointment
                WHERE patient_id IN ('MHS-PAT-001', 'MHS-PAT-002', 'MHS-PAT-003')
                """,
                Integer.class);
        assertThat(historical).isZero();
        Integer offset = jdbc.queryForObject(
                "SELECT start_offset_days FROM appointment WHERE appointment_id = 'MHS-APT-002'",
                Integer.class);
        store.ensureReady();
        assertThat(jdbc.queryForObject(
                "SELECT start_offset_days FROM appointment WHERE appointment_id = 'MHS-APT-002'",
                Integer.class)).isEqualTo(offset);

        jdbc.execute("ALTER TABLE appointment RENAME TO appointment_hidden");
        try {
            mockMvc.perform(get("/appointments").param("patientId", "MHS-PAT-004"))
                    .andExpect(status().isServiceUnavailable())
                    .andExpect(jsonPath("$.error").value("unavailable"));
        } finally {
            jdbc.execute("ALTER TABLE appointment_hidden RENAME TO appointment");
        }
    }

    @Test
    void sourcesDoNotDependOnFhirOrTheOtherServices() throws Exception {
        String pom = Files.readString(Path.of("pom.xml"));
        assertThat(pom).doesNotContainIgnoringCase("hapi");
        assertThat(pom).doesNotContainIgnoringCase("fhir-integration");
        assertThat(pom).doesNotContain("ca.uhn");

        StringBuilder sources = new StringBuilder();
        try (Stream<Path> files = Files.walk(Path.of("src/main/java"))) {
            files.filter(path -> path.toString().endsWith(".java")).forEach(path -> {
                try {
                    sources.append(Files.readString(path));
                } catch (Exception ex) {
                    throw new IllegalStateException(path.toString(), ex);
                }
            });
        }
        String text = sources.toString();
        assertThat(text).doesNotContain("org.hl7.fhir");
        assertThat(text).doesNotContain("ca.uhn");
        assertThat(text).doesNotContain("resourceType");
        assertThat(text).doesNotContain("8080");
        assertThat(text).doesNotContain("8081");
        assertThat(text).doesNotContain("8090");
        assertThat(text).doesNotContain("lab.healthcare.fhir");
        assertThatThrownBy(() -> Class.forName("ca.uhn.fhir.context.FhirContext"))
                .isInstanceOf(ClassNotFoundException.class);
        assertThat(LoopbackGuard.isLoopback("127.0.0.1")).isTrue();
        assertThat(LoopbackGuard.isLoopback("0.0.0.0")).isFalse();
    }
}
