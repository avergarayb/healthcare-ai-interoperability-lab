package lab.healthcare.fhir.aiconsumeraccess.web;

import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
import lab.healthcare.fhir.aiconsumer.AiConsumerContract;
import lab.healthcare.fhir.aiconsumer.AiConsumerContractService;
import lab.healthcare.fhir.aiconsumeraccess.AiConsumerClinicalDataAccessBoundary;
import lab.healthcare.fhir.aiconsumeraccess.AiConsumerClinicalDataAccessResult;
import lab.healthcare.fhir.aiconsumerauthorization.AiConsumerAuthorizationBoundary;
import lab.healthcare.fhir.aiconsumerauthorization.AiConsumerAuthorizationResult;
import lab.healthcare.fhir.aiconsumerconsent.AiConsumerConsentBoundary;
import lab.healthcare.fhir.aiconsumerconsent.AiConsumerConsentResult;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicy;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyInput;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyResult;
import lab.healthcare.fhir.aiconsumerreadiness.AiConsumerReadiness;
import lab.healthcare.fhir.aiconsumerreadiness.AiConsumerReadinessResult;
import lab.healthcare.fhir.aiconsumerscope.AiConsumerDataScopeBoundary;
import lab.healthcare.fhir.aiconsumerscope.AiConsumerDataScopeResult;
import lab.healthcare.fhir.aihandoffauthorization.AiHandoffAuthorizationBoundary;
import lab.healthcare.fhir.aihandoffauthorization.AiHandoffAuthorizationResult;
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
 * Laboratory surfaces for clinical data-access request enforcement.
 * Deny-by-default. Not real access, not FHIR, and not a model runtime.
 */
@RestController
public class AiConsumerClinicalDataAccessController {

    private static final Logger log = LoggerFactory.getLogger(AiConsumerClinicalDataAccessController.class);

    private final ModelBoundaryContractProvider provider;

    public AiConsumerClinicalDataAccessController(ModelBoundaryContractProvider provider) {
        if (provider == null) {
            throw new IllegalArgumentException("Model boundary contract provider must be provided");
        }
        this.provider = provider;
    }

    @GetMapping(path = "/lab/ai-consumer-clinical-data-access", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> labPage() {
        Evaluated evaluated = evaluate();
        return ResponseEntity.status(evaluated.httpStatus())
                .body(SmartLabPages.aiConsumerClinicalDataAccess(evaluated.result()));
    }

    @GetMapping(path = "/api/ai-consumer-clinical-data-access/v1", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<AiConsumerClinicalDataAccessResult> payload() {
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
        AiConsumerReadinessResult readiness = AiConsumerReadiness.evaluate(policy);
        AiHandoffAuthorizationResult handoff = AiHandoffAuthorizationBoundary.evaluate(readiness);
        AiConsumerAuthorizationResult authorization = AiConsumerAuthorizationBoundary.evaluate(handoff);
        AiConsumerConsentResult consent = AiConsumerConsentBoundary.evaluate(authorization);
        AiConsumerDataScopeResult scope = AiConsumerDataScopeBoundary.evaluate(consent);
        AiConsumerClinicalDataAccessResult result = AiConsumerClinicalDataAccessBoundary.evaluate(scope);
        log.info(
                "AI consumer clinical data access status={} reason={} operation={}",
                result.status(),
                result.reason(),
                result.operation());
        return new Evaluated(result, ModelBoundaryHttpStatuses.of(contract.outcome()));
    }

    private record Evaluated(AiConsumerClinicalDataAccessResult result, int httpStatus) {
    }
}
