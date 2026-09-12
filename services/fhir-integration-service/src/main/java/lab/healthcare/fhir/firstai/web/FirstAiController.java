package lab.healthcare.fhir.firstai.web;

import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
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
 * Laboratory surfaces for the first isolated AI component. Not an ai-service
 * and not a model runtime.
 */
@RestController
public class FirstAiController {

    private static final Logger log = LoggerFactory.getLogger(FirstAiController.class);

    private final ModelBoundaryContractProvider provider;

    public FirstAiController(ModelBoundaryContractProvider provider) {
        if (provider == null) {
            throw new IllegalArgumentException("Model boundary contract provider must be provided");
        }
        this.provider = provider;
    }

    @GetMapping(path = "/lab/first-ai-component", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> labPage() {
        Processed processed = process();
        return ResponseEntity.status(processed.httpStatus()).body(SmartLabPages.firstAiComponent(processed.result()));
    }

    @GetMapping(path = "/api/first-ai-component/v1", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<FirstAiResult> payload() {
        Processed processed = process();
        return ResponseEntity.status(processed.httpStatus()).body(processed.result());
    }

    private Processed process() {
        ModelBoundaryContract contract = provider.currentContract();
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(contract);
        DeterministicAgentResult agent =
                DeterministicAgent.evaluate(DeterministicAgentInput.of(contract, diagnosis));
        AiBoundaryResult boundary = AiBoundaryService.prepare(AiBoundaryInput.of(contract, diagnosis, agent));
        FirstAiResult result = FirstAiComponent.process(boundary);
        log.info(
                "First AI component destination={} componentStatus={} processingStatus={} agentDecision={} pipeline={} clinicalDataAvailable={} modelCalled={} modelCallAuthorized={} reason={} warningCount={}",
                result.destination(),
                result.componentStatus(),
                result.processingStatus(),
                result.agentDecision(),
                result.pipelineStatus(),
                result.clinicalDataAvailable(),
                result.modelCalled(),
                result.modelCallAuthorized(),
                result.reasonCode(),
                result.warnings().size());
        return new Processed(result, ModelBoundaryHttpStatuses.of(contract.outcome()));
    }

    private record Processed(FirstAiResult result, int httpStatus) {
    }
}
