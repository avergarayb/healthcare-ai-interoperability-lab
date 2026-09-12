package lab.healthcare.fhir.aigateway.web;

import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
import lab.healthcare.fhir.aigateway.AiExecutionDecision;
import lab.healthcare.fhir.aigateway.AiExecutionGate;
import lab.healthcare.fhir.firstai.FirstAiComponent;
import lab.healthcare.fhir.firstai.FirstAiResult;
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
 * Laboratory surfaces for the AI execution gate. Not an ai-service and not a
 * model runtime.
 */
@RestController
public class AiExecutionGateController {

    private static final Logger log = LoggerFactory.getLogger(AiExecutionGateController.class);

    private final ModelBoundaryContractProvider provider;

    public AiExecutionGateController(ModelBoundaryContractProvider provider) {
        if (provider == null) {
            throw new IllegalArgumentException("Model boundary contract provider must be provided");
        }
        this.provider = provider;
    }

    @GetMapping(path = "/lab/ai-execution-gate", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> labPage() {
        Evaluated evaluated = evaluate();
        return ResponseEntity.status(evaluated.httpStatus()).body(SmartLabPages.aiExecutionGate(evaluated.result()));
    }

    @GetMapping(path = "/api/ai-execution-gate/v1", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<AiExecutionDecision> payload() {
        Evaluated evaluated = evaluate();
        return ResponseEntity.status(evaluated.httpStatus()).body(evaluated.result());
    }

    private Evaluated evaluate() {
        ModelBoundaryContract contract = provider.currentContract();
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(contract);
        DeterministicAgentResult agent =
                DeterministicAgent.evaluate(DeterministicAgentInput.of(contract, diagnosis));
        AiBoundaryResult boundary = AiBoundaryService.prepare(AiBoundaryInput.of(contract, diagnosis, agent));
        FirstAiResult firstAi = FirstAiComponent.process(boundary);
        AiExecutionDecision result = AiExecutionGate.evaluate(firstAi);
        log.info(
                "AI execution gate destination={} executionDecision={} processingStatus={} agentDecision={} pipeline={} clinicalDataAvailable={} modelCalled={} modelCallAuthorized={} reason={} executionReason={} warningCount={}",
                result.destination(),
                result.executionDecision(),
                result.processingStatus(),
                result.agentDecision(),
                result.pipelineStatus(),
                result.clinicalDataAvailable(),
                result.modelCalled(),
                result.modelCallAuthorized(),
                result.reasonCode(),
                result.executionReason(),
                result.warnings().size());
        return new Evaluated(result, ModelBoundaryHttpStatuses.of(contract.outcome()));
    }

    private record Evaluated(AiExecutionDecision result, int httpStatus) {
    }
}
