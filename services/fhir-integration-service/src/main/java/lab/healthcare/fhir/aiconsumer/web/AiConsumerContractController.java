package lab.healthcare.fhir.aiconsumer.web;

import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
import lab.healthcare.fhir.aiconsumer.AiConsumerContract;
import lab.healthcare.fhir.aiconsumer.AiConsumerContractService;
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
 * Laboratory surfaces for AI Consumer Contract v1. Not a public consumer API
 * and not a model runtime.
 */
@RestController
public class AiConsumerContractController {

    private static final Logger log = LoggerFactory.getLogger(AiConsumerContractController.class);

    private final ModelBoundaryContractProvider provider;

    public AiConsumerContractController(ModelBoundaryContractProvider provider) {
        if (provider == null) {
            throw new IllegalArgumentException("Model boundary contract provider must be provided");
        }
        this.provider = provider;
    }

    @GetMapping(path = "/lab/ai-consumer-contract", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> labPage() {
        Prepared prepared = prepare();
        return ResponseEntity.status(prepared.httpStatus()).body(SmartLabPages.aiConsumerContract(prepared.result()));
    }

    @GetMapping(path = "/api/ai-consumer-contract/v1", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<AiConsumerContract> payload() {
        Prepared prepared = prepare();
        return ResponseEntity.status(prepared.httpStatus()).body(prepared.result());
    }

    private Prepared prepare() {
        ModelBoundaryContract contract = provider.currentContract();
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(contract);
        DeterministicAgentResult agent =
                DeterministicAgent.evaluate(DeterministicAgentInput.of(contract, diagnosis));
        AiBoundaryResult boundary = AiBoundaryService.prepare(AiBoundaryInput.of(contract, diagnosis, agent));
        FirstAiResult firstAi = FirstAiComponent.process(boundary);
        AiExecutionDecision gate = AiExecutionGate.evaluate(firstAi);
        AiConsumerContract result = AiConsumerContractService.prepare(gate);
        log.info(
                "AI consumer contract destination={} version={} contractStatus={} dispatchStatus={} executionDecision={} pipeline={} clinicalDataAvailable={} modelCalled={} modelCallAuthorized={} reasonCount={} warningCount={}",
                result.destination(),
                result.contractVersion(),
                result.contractStatus(),
                result.dispatchStatus(),
                result.executionDecision(),
                result.pipelineStatus(),
                result.clinicalDataAvailable(),
                result.modelCalled(),
                result.modelCallAuthorized(),
                result.reasonCodes().size(),
                result.warnings().size());
        return new Prepared(result, ModelBoundaryHttpStatuses.of(contract.outcome()));
    }

    private record Prepared(AiConsumerContract result, int httpStatus) {
    }
}
