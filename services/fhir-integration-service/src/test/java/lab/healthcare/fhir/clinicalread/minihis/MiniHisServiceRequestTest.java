package lab.healthcare.fhir.clinicalread.minihis;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class MiniHisServiceRequestTest {

    @Test
    void submittedOrderKeepsTheExchangeIdentifiersAndTheSourceCode() throws Exception {
        ObjectNode order = new ObjectMapper().readValue(
                """
                {"orderId":"MHS-LAB-001","patientId":"MHS-PAT-001","destinationSystemKey":"mini-lis",
                 "testCode":"GLU","testDescription":"Glucose","requestedAt":"2026-03-01T10:00:00Z",
                 "localStatus":"submitted","correlationId":"EXC-001","destinationOrderId":"MLS-ORD-001",
                 "destinationOrganizationId":"org-mini-lis"}
                """,
                ObjectNode.class);
        ObjectNode resource = new MiniHisNormalizer(new ObjectMapper()).serviceRequest(order);
        assertThat(resource.path("resourceType").asText()).isEqualTo("ServiceRequest");
        assertThat(resource.path("status").asText()).isEqualTo("active");
        assertThat(resource.path("meta").path("source").asText()).isEqualTo("https://lab.local/mini-his");
        assertThat(resource.path("code").path("coding").get(0).path("system").asText())
                .isEqualTo("https://lab.local/mini-his/test");
        assertThat(resource.path("code").path("coding").get(0).path("code").asText()).isEqualTo("GLU");
        assertThat(resource.path("identifier").findValuesAsText("value"))
                .contains("MHS-LAB-001", "EXC-001", "MLS-ORD-001");
    }
}
