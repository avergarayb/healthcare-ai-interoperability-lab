package lab.healthcare.fhir.exchange;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class MiniLisExchangeConnectorTest {

    private final ObjectMapper json = new ObjectMapper();

    @Test
    void selectsOnlyThePatientOfTheRequestedSystem() throws Exception {
        var body = json.readTree("""
                [
                  {"patientId":"MLS-A","identifierSystem":"https://lab.local/mini-his/patient"},
                  {"patientId":"MLS-B","identifierSystem":"https://lab.local/other-system/patient"}
                ]
                """);
        assertThat(MiniLisExchangeConnector.selectPatientId(body, "https://lab.local/mini-his/patient")).isEqualTo("MLS-A");
        assertThat(MiniLisExchangeConnector.selectPatientId(body, "https://lab.local/other-system/patient")).isEqualTo("MLS-B");
        assertThat(MiniLisExchangeConnector.selectPatientId(body, "https://lab.local/missing/patient")).isNull();
        assertThat(MiniLisExchangeConnector.ambiguous(body, "https://lab.local/mini-his/patient")).isFalse();
    }

    @Test
    void twoMatchesOfTheSameSystemAreAmbiguous() throws Exception {
        var body = json.readTree("""
                [
                  {"patientId":"MLS-A","identifierSystem":"https://lab.local/mini-his/patient"},
                  {"patientId":"MLS-C","identifierSystem":"https://lab.local/mini-his/patient"}
                ]
                """);
        assertThat(MiniLisExchangeConnector.ambiguous(body, "https://lab.local/mini-his/patient")).isTrue();
        assertThat(MiniLisExchangeConnector.selectPatientId(body, "https://lab.local/mini-his/patient")).isNull();
    }
}
