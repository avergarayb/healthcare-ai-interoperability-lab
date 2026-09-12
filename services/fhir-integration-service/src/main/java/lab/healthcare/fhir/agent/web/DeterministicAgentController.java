package lab.healthcare.fhir.agent.web;

import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractProvider;
import lab.healthcare.fhir.modelboundary.ModelBoundaryHttpStatuses;
import lab.healthcare.fhir.pipeline.PipelineDiagnoses;
import lab.healthcare.fhir.smart.web.SmartLabPages;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Laboratory surfaces for the deterministic boundary agent. HTML and JSON
 * expose the verdict only. Not a model runtime and not a clinical API.
 */
@RestController
public class DeterministicAgentController {

    private static final Logger log = LoggerFactory.getLogger(DeterministicAgentController.class);

    private final ModelBoundaryContractProvider provider;

    public DeterministicAgentController(ModelBoundaryContractProvider provider) {
        if (provider == null) {
            throw new IllegalArgumentException("Model boundary contract provider must be provided");
        }
        this.provider = provider;
    }

    @GetMapping(path = "/lab/deterministic-agent", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> labPage() {
        Evaluated evaluated = evaluate();
        return ResponseEntity.status(evaluated.httpStatus()).body(SmartLabPages.deterministicAgent(evaluated.result()));
    }

    @GetMapping(path = "/api/deterministic-agent/v1", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<DeterministicAgentResult> observation() {
        Evaluated evaluated = evaluate();
        return ResponseEntity.status(evaluated.httpStatus()).body(evaluated.result());
    }

    private Evaluated evaluate() {
        ModelBoundaryContract contract = provider.currentContract();
        DeterministicAgentResult result =
                DeterministicAgent.evaluate(DeterministicAgentInput.of(contract, PipelineDiagnoses.fromContract(contract)));
        log.info(
                "Deterministic agent destination={} decision={} reason={} pipeline={} contractValid={} usable={} warningCount={} modelCalled={}",
                contract.destination(),
                result.decision(),
                result.reasonCode(),
                result.pipelineStatus(),
                result.contractValid(),
                result.usable(),
                result.warnings().size(),
                result.modelCalled());
        return new Evaluated(result, ModelBoundaryHttpStatuses.of(contract.outcome()));
    }

    private record Evaluated(DeterministicAgentResult result, int httpStatus) {
    }
}
