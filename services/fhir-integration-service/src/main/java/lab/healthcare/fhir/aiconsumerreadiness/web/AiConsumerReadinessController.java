package lab.healthcare.fhir.aiconsumerreadiness.web;

import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
import lab.healthcare.fhir.aiconsumer.AiConsumerContract;
import lab.healthcare.fhir.aiconsumer.AiConsumerContractService;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicy;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyInput;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyResult;
import lab.healthcare.fhir.aiconsumerreadiness.AiConsumerReadiness;
import lab.healthcare.fhir.aiconsumerreadiness.AiConsumerReadinessResult;
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
 * Laboratory surfaces for AI consumer readiness. Uses a synthetic lab
 * consumer. Not real authentication, not handoff, and not a model runtime.
 */
@RestController
public class AiConsumerReadinessController {

    private static final Logger log = LoggerFactory.getLogger(AiConsumerReadinessController.class);

    private final ModelBoundaryContractProvider provider;

    public AiConsumerReadinessController(ModelBoundaryContractProvider provider) {
        if (provider == null) {
            throw new IllegalArgumentException("Model boundary contract provider must be provided");
        }
        this.provider = provider;
    }

    @GetMapping(path = "/lab/ai-consumer-readiness", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> labPage() {
        Evaluated evaluated = evaluate();
        return ResponseEntity.status(evaluated.httpStatus()).body(SmartLabPages.aiConsumerReadiness(evaluated.result()));
    }

    @GetMapping(path = "/api/ai-consumer-readiness/v1", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<AiConsumerReadinessResult> payload() {
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
        AiExecutionDecision gate = AiExecutionGate.evaluate(firstAi);
        AiConsumerContract consumerContract = AiConsumerContractService.prepare(gate);
        AiConsumerPolicyResult policy = AiConsumerPolicy.evaluate(AiConsumerPolicyInput.laboratory(consumerContract));
        AiConsumerReadinessResult result = AiConsumerReadiness.evaluate(policy);
        log.info(
                "AI consumer readiness status={} reason={} policy={} version={} consumerType={} operation={} scope={} modelCalled={} modelCallAuthorized={} dispatch={} handoffAuthorized={} dispatchPerformed={}",
                result.readinessStatus(),
                result.reasonCode(),
                result.policyDecision(),
                result.contractVersion(),
                result.consumerType(),
                result.requestedOperation(),
                result.requestedScope(),
                result.modelCalled(),
                result.modelCallAuthorized(),
                result.dispatchStatus(),
                result.handoffAuthorized(),
                result.dispatchPerformed());
        return new Evaluated(result, ModelBoundaryHttpStatuses.of(contract.outcome()));
    }

    private record Evaluated(AiConsumerReadinessResult result, int httpStatus) {
    }
}
