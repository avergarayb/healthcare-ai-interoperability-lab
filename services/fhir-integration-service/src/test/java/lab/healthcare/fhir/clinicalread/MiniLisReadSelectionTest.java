package lab.healthcare.fhir.clinicalread;

import lab.healthcare.fhir.clinicalread.minihis.MiniHisClinicalSource;
import lab.healthcare.fhir.clinicalread.minilis.MiniLisClinicalSource;
import lab.healthcare.fhir.routing.RoutingService;
import lab.healthcare.fhir.server.FhirServersProperties;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;

class MiniLisReadSelectionTest {

    @Test
    void serviceRequestsStayUnsupportedUntilTheSourceIsMiniLis() {
        ClinicalReadService local = new ClinicalReadService(
                mock(RoutingService.class),
                new FhirServersProperties("local-hapi", Map.of()),
                new ObjectMapper());
        assertThatThrownBy(() -> local.readServiceRequest("MLS-ORD-001"))
                .isInstanceOf(ClinicalReadException.class)
                .hasMessage("operation_not_supported");
        assertThatThrownBy(() -> local.readDiagnosticReport("MLS-ORD-001"))
                .isInstanceOf(ClinicalReadException.class)
                .hasMessage("operation_not_supported");
    }

    @Test
    void miniLisDoesNotServeEncountersOrAppointments() {
        ClinicalReadService lis = new ClinicalReadService(
                mock(RoutingService.class),
                new FhirServersProperties("local-hapi", Map.of()),
                new ObjectMapper(),
                "mini-lis",
                (MiniHisClinicalSource) null,
                (MiniLisClinicalSource) null);
        assertThatThrownBy(() -> lis.readEncounter("MLS-ORD-001"))
                .isInstanceOf(ClinicalReadException.class)
                .hasMessage("operation_not_supported");
        assertThatThrownBy(() -> lis.searchAppointments("MLS-PAT-001"))
                .isInstanceOf(ClinicalReadException.class)
                .hasMessage("operation_not_supported");
    }
}
