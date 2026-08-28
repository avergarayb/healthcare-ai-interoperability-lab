package lab.healthcare.fhir.routing;

import org.hl7.fhir.r4.model.Patient;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class RoutingRequestTest {

    @Test
    void readPatientSetsDestinationAndLogicalId() {
        RoutingRequest request = RoutingRequest.readPatient("local-hapi", "patient-001");

        assertThat(request.destination()).isEqualTo("local-hapi");
        assertThat(request.resource()).isInstanceOf(Patient.class);
        assertThat(request.resource().getIdElement().getIdPart()).isEqualTo("patient-001");
    }

    @Test
    void rejectsBlankDestination() {
        assertThatThrownBy(() -> new RoutingRequest(" ", new Patient()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("destination");
    }

    @Test
    void rejectsMissingResource() {
        assertThatThrownBy(() -> new RoutingRequest("local-hapi", null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("resource");
    }
}
