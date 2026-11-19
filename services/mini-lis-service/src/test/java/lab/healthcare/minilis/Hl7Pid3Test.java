package lab.healthcare.minilis;

import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.time.OffsetDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class Hl7Pid3Test {

    private final Hl7Messages messages = new Hl7Messages();

    @Test
    void theIdentifierSystemIsTheAssigningAuthorityUniversalId() throws Exception {
        Hl7Messages.ParsedMessage parsed = messages.parse(order("CASE-1", "https://lab.local/mini-his/patient"));
        assertEquals("org-mini-his", Hl7Messages.assigningOrganization(parsed.terser(), "/PATIENT/PID"));
        assertEquals("https://lab.local/mini-his/patient", Hl7Messages.value(parsed.terser(), "/PATIENT/PID-3-4-2"));
        assertEquals("URI", Hl7Messages.value(parsed.terser(), "/PATIENT/PID-3-4-3"));
        assertEquals("https://lab.local/mini-his/patient", Hl7Messages.patientIdentifierSystem(parsed.terser(), "/PATIENT/PID"));
        assertTrue(Hl7Messages.value(parsed.terser(), "/PATIENT/PID-3-10").isEmpty());
    }

    @Test
    void aDepartmentIsNotAnIdentifierSystemAndAContradictionIsRejected() throws Exception {
        Hl7Messages.ParsedMessage department = messages.parse(order("CASE-2", "https://lab.local/mini-his/patient"));
        department.terser().set("/PATIENT/PID-3-10", "LAB-CHEM");
        assertEquals("https://lab.local/mini-his/patient", Hl7Messages.patientIdentifierSystem(department.terser(), "/PATIENT/PID"));

        Hl7Messages.ParsedMessage legacy = messages.parse(order("CASE-3", ""));
        legacy.terser().set("/PATIENT/PID-3-10", "https://lab.local/mini-his/patient");
        assertEquals("https://lab.local/mini-his/patient", Hl7Messages.patientIdentifierSystem(legacy.terser(), "/PATIENT/PID"));

        Hl7Messages.ParsedMessage omitted = messages.parse(order("CASE-4", ""));
        omitted.terser().set("/PATIENT/PID-3-10", "LAB-CHEM");
        assertEquals("", Hl7Messages.patientIdentifierSystem(omitted.terser(), "/PATIENT/PID"));

        Hl7Messages.ParsedMessage contradictory = messages.parse(order("CASE-5", "https://lab.local/mini-his/patient"));
        contradictory.terser().set("/PATIENT/PID-3-10", "https://lab.local/other-system/patient");
        assertNull(Hl7Messages.patientIdentifierSystem(contradictory.terser(), "/PATIENT/PID"));
    }

    private String order(String externalId, String identifierSystem) {
        return messages.oml(new Hl7Messages.OmlPayload(
                "FHIR-EXCHANGE",
                "fhir-integration-service",
                "MINI-LIS",
                "org-mini-lis",
                "secret",
                "MSG-" + externalId,
                "org-mini-his",
                externalId,
                "Quispe",
                "Ana",
                LocalDate.parse("1984-03-12"),
                "female",
                "MHS-LAB-" + externalId,
                "GLU",
                "Glucose",
                "https://lab.local/mini-his/test",
                OffsetDateTime.parse("2026-03-01T10:00:00Z")), identifierSystem);
    }
}
