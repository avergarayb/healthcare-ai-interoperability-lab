package lab.healthcare.fhir.patient;

import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class PatientContextsTest {

    @Test
    void missingIdYieldsEmptyContext() {
        assertThat(PatientContexts.configured("oracle-health-sandbox", null)).isEmpty();
        assertThat(PatientContexts.configured("oracle-health-sandbox", "")).isEmpty();
        assertThat(PatientContexts.configured("oracle-health-sandbox", "   ")).isEmpty();
    }

    @Test
    void missingDestinationYieldsEmptyContext() {
        assertThat(PatientContexts.configured(null, "lab-configured-patient")).isEmpty();
        assertThat(PatientContexts.configured("  ", "lab-configured-patient")).isEmpty();
    }

    @Test
    void validConfiguredIdBuildsContextWithoutLeakingIdentifier() {
        Optional<PatientContext> context = PatientContexts.configured(
                "oracle-health-sandbox", "  lab-configured-patient  ");

        assertThat(context).isPresent();
        assertThat(context.orElseThrow().destination()).isEqualTo("oracle-health-sandbox");
        assertThat(context.orElseThrow().patientId()).isEqualTo("lab-configured-patient");
        assertThat(context.orElseThrow().source()).isEqualTo(PatientContextSource.CONFIGURED);
        assertThat(context.orElseThrow().toString()).doesNotContain("lab-configured-patient");
        assertThat(context.orElseThrow().toString()).contains("hasPatientId=true");
    }

    @Test
    void patientContextRequiresNonBlankFields() {
        assertThatThrownBy(() -> new PatientContext(" ", "lab-configured-patient", PatientContextSource.CONFIGURED))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Destination");
        assertThatThrownBy(() -> new PatientContext("oracle-health-sandbox", " ", PatientContextSource.CONFIGURED))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Patient identifier");
        assertThatThrownBy(() -> new PatientContext("oracle-health-sandbox", "lab-configured-patient", null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("source");
    }
}
