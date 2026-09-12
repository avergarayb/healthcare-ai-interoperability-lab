package lab.healthcare.fhir.aiboundary.web;

import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractProvider;
import lab.healthcare.fhir.modelboundary.ModelBoundaryHttpStatuses;
import lab.healthcare.fhir.pipeline.PipelineDiagnoses;
import lab.healthcare.fhir.pipeline.PipelineDiagnosis;
import lab.healthcare.fhir.smart.web.SmartLabPages;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Laboratory surfaces for the AI boundary payload. Not an ai-service and not a
 * model runtime.
 */
@RestController
public class AiBoundaryController {

    private static final Logger log = LoggerFactory.getLogger(AiBoundaryController.class);

    private final ModelBoundaryContractProvider provider;

    public AiBoundaryController(ModelBoundaryContractProvider provider) {
        if (provider == null) {
            throw new IllegalArgumentException("Model boundary contract provider must be provided");
        }
        this.provider = provider;
    }

    @GetMapping(path = "/lab/ai-boundary", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> labPage() {
        Prepared prepared = prepare();
        return ResponseEntity.status(prepared.httpStatus()).body(SmartLabPages.aiBoundary(prepared.result()));
    }

    @GetMapping(path = "/api/ai-boundary/v1", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<AiBoundaryResult> payload() {
        Prepared prepared = prepare();
        return ResponseEntity.status(prepared.httpStatus()).body(prepared.result());
    }

    private Prepared prepare() {
        ModelBoundaryContract contract = provider.currentContract();
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(contract);
        DeterministicAgentResult agent =
                DeterministicAgent.evaluate(DeterministicAgentInput.of(contract, diagnosis));
        AiBoundaryResult result = AiBoundaryService.prepare(AiBoundaryInput.of(contract, diagnosis, agent));
        log.info(
                "AI boundary destination={} agentDecision={} pipeline={} clinicalDataAvailable={} modelCalled={} modelCallAuthorized={} reason={} warningCount={}",
                result.destination(),
                result.decision().agentDecision(),
                result.decision().pipelineStatus(),
                result.decision().clinicalDataAvailable(),
                result.decision().modelCalled(),
                result.decision().modelCallAuthorized(),
                result.reasonCode(),
                result.warnings().size());
        return new Prepared(result, ModelBoundaryHttpStatuses.of(contract.outcome()));
    }

    private record Prepared(AiBoundaryResult result, int httpStatus) {
    }
}
