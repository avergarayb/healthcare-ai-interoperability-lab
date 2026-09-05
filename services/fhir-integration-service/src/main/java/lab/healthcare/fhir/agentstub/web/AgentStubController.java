package lab.healthcare.fhir.agentstub.web;

import lab.healthcare.fhir.agentstub.AgentStub;
import lab.healthcare.fhir.agentstub.AgentStubObservation;
import lab.healthcare.fhir.agentstub.ObservedCollection;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractProvider;
import lab.healthcare.fhir.modelboundary.ModelBoundaryHttpStatuses;
import lab.healthcare.fhir.smart.web.SmartLabPages;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Laboratory surfaces for the contract-consuming stub. HTML and JSON expose
 * observation metadata only. Not a model runtime.
 */
@RestController
public class AgentStubController {

    private static final Logger log = LoggerFactory.getLogger(AgentStubController.class);

    private final ModelBoundaryContractProvider provider;

    public AgentStubController(ModelBoundaryContractProvider provider) {
        if (provider == null) {
            throw new IllegalArgumentException("Model boundary contract provider must be provided");
        }
        this.provider = provider;
    }

    @GetMapping(path = "/lab/agent-stub", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> labPage() {
        AgentStubObservation observation = observe();
        return ResponseEntity.status(ModelBoundaryHttpStatuses.of(observation.outcome())).body(page(observation));
    }

    @GetMapping(path = "/api/agent-stub/v1", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<AgentStubObservation> observation() {
        AgentStubObservation observation = observe();
        return ResponseEntity.status(ModelBoundaryHttpStatuses.of(observation.outcome())).body(observation);
    }

    private AgentStubObservation observe() {
        AgentStubObservation observation = AgentStub.observe(provider.currentContract());
        log.info(
                "Agent stub consumed contractVersion={} destination={} outcome={} patient={} conditions={} observations={} diagnosticReports={} medicationRequests={} modelCalled={}",
                observation.contractVersion(),
                observation.destination(),
                observation.outcome(),
                observation.patientStatus(),
                collectionLog(observation.conditions()),
                collectionLog(observation.observations()),
                collectionLog(observation.diagnosticReports()),
                collectionLog(observation.medicationRequests()),
                observation.modelCalled());
        return observation;
    }

    private static String page(AgentStubObservation observation) {
        return SmartLabPages.error(
                "Contract-consuming agent stub",
                "contractVersion=" + observation.contractVersion()
                        + " outcome=" + observation.outcome()
                        + " destination=" + observation.destination()
                        + " contextSource=" + observation.contextSource()
                        + " patient=" + observation.patientStatus()
                        + " " + collectionLine("conditions", observation.conditions())
                        + " " + collectionLine("observations", observation.observations())
                        + " " + collectionLine("diagnosticReports", observation.diagnosticReports())
                        + " " + collectionLine("medicationRequests", observation.medicationRequests())
                        + " consumed=" + observation.consumed()
                        + " modelCalled=" + observation.modelCalled());
    }

    private static String collectionLine(String name, ObservedCollection collection) {
        if (collection == null || collection.status() == null) {
            return name + "=";
        }
        return name + "=" + collection.status()
                + " " + name + "ReceivedCount=" + collection.receivedCount()
                + " " + name + "RetainedCount=" + collection.retainedCount()
                + " " + name + "Truncated=" + collection.truncated();
    }

    private static String collectionLog(ObservedCollection collection) {
        if (collection == null || collection.status() == null) {
            return "";
        }
        return collection.status()
                + " receivedCount=" + collection.receivedCount()
                + " retainedCount=" + collection.retainedCount()
                + " truncated=" + collection.truncated();
    }
}
