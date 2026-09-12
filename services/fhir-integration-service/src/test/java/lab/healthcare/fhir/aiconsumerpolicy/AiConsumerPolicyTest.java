package lab.healthcare.fhir.aiconsumerpolicy;

import lab.healthcare.fhir.agent.AgentDecision;
import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
import lab.healthcare.fhir.aiconsumer.AiConsumerContract;
import lab.healthcare.fhir.aiconsumer.AiConsumerContractService;
import lab.healthcare.fhir.aiconsumer.AiConsumerDispatchStatus;
import lab.healthcare.fhir.aiconsumer.AiConsumerReasonCodes;
import lab.healthcare.fhir.aigateway.AiExecutionGate;
import lab.healthcare.fhir.aigateway.AiExecutionInput;
import lab.healthcare.fhir.firstai.FirstAiComponent;
import lab.healthcare.fhir.firstai.FirstAiComponentStatus;
import lab.healthcare.fhir.firstai.FirstAiProcessingStatus;
import lab.healthcare.fhir.firstai.FirstAiResult;
import lab.healthcare.fhir.modelboundary.BoundaryCollection;
import lab.healthcare.fhir.modelboundary.BoundaryCondition;
import lab.healthcare.fhir.modelboundary.BoundaryDiagnosticReport;
import lab.healthcare.fhir.modelboundary.BoundaryObservation;
import lab.healthcare.fhir.modelboundary.BoundaryPatient;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractVersion;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.pipeline.PipelineDiagnoses;
import lab.healthcare.fhir.pipeline.PipelineDiagnosis;
import lab.healthcare.fhir.pipeline.PipelineStageStatus;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AiConsumerPolicyTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T22:00:00Z");

    @Test
    void validLaboratoryConsumerIsAllowedForFutureConsumption() {
        AiConsumerPolicyResult result = evaluate(readyContract(), AiConsumerIdentity.laboratory());

        assertThat(result.decision()).isEqualTo(AiConsumerPolicyDecision.ALLOWED_FOR_FUTURE_CONSUMPTION);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerPolicyReasonCodes.ALLOWED_FOR_FUTURE_CONSUMPTION);
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.processingStatus()).isEqualTo(FirstAiProcessingStatus.NOT_EXECUTED);
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerDispatchStatus.NOT_DISPATCHED);
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Patient/");
    }

    @Test
    void unauthenticatedConsumerIsRejected() {
        AiConsumerPolicyResult result = evaluate(readyContract(), laboratory(false, true, true, "v1",
                AiConsumerPolicyOperations.READ_CONTRACT, AiConsumerPolicyScopes.CONTRACT_READ));

        assertThat(result.decision()).isEqualTo(AiConsumerPolicyDecision.REJECTED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerPolicyReasonCodes.CONSUMER_NOT_AUTHENTICATED);
        assertThat(result.modelCallAuthorized()).isFalse();
    }

    @Test
    void unauthorizedConsumerIsRejected() {
        AiConsumerPolicyResult result = evaluate(readyContract(), laboratory(true, false, true, "v1",
                AiConsumerPolicyOperations.READ_CONTRACT, AiConsumerPolicyScopes.CONTRACT_READ));

        assertThat(result.decision()).isEqualTo(AiConsumerPolicyDecision.REJECTED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerPolicyReasonCodes.CONSUMER_NOT_AUTHORIZED);
    }

    @Test
    void missingScopeIsRejected() {
        AiConsumerPolicyResult result = evaluate(readyContract(), laboratory(true, true, true, "v1",
                AiConsumerPolicyOperations.READ_CONTRACT, "ai.model.execute"));

        assertThat(result.decision()).isEqualTo(AiConsumerPolicyDecision.REJECTED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerPolicyReasonCodes.REQUIRED_SCOPE_MISSING);
    }

    @Test
    void incompatibleVersionIsRejected() {
        AiConsumerPolicyResult result = evaluate(readyContract(), laboratory(true, true, true, "v2",
                AiConsumerPolicyOperations.READ_CONTRACT, AiConsumerPolicyScopes.CONTRACT_READ));

        assertThat(result.decision()).isEqualTo(AiConsumerPolicyDecision.REJECTED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerPolicyReasonCodes.CONTRACT_VERSION_NOT_SUPPORTED);
    }

    @Test
    void forbiddenOperationIsRejected() {
        AiConsumerPolicyResult result = evaluate(readyContract(), laboratory(true, true, true, "v1",
                AiConsumerPolicyOperations.EXECUTE_MODEL, AiConsumerPolicyScopes.CONTRACT_READ));

        assertThat(result.decision()).isEqualTo(AiConsumerPolicyDecision.REJECTED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerPolicyReasonCodes.OPERATION_NOT_ALLOWED);
        assertThat(result.modelCallAuthorized()).isFalse();
    }

    @Test
    void missingTenantContextIsRejected() {
        AiConsumerPolicyResult result = evaluate(readyContract(), laboratory(true, true, false, "v1",
                AiConsumerPolicyOperations.READ_CONTRACT, AiConsumerPolicyScopes.CONTRACT_READ));

        assertThat(result.decision()).isEqualTo(AiConsumerPolicyDecision.REJECTED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerPolicyReasonCodes.TENANT_CONTEXT_REQUIRED);
    }

    @Test
    void blockedContractIsNotConsumable() {
        AiConsumerPolicyResult result = evaluate(blockedContract(), AiConsumerIdentity.laboratory());

        assertThat(result.decision()).isEqualTo(AiConsumerPolicyDecision.REJECTED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerPolicyReasonCodes.CONTRACT_NOT_CONSUMABLE);
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerDispatchStatus.NOT_DISPATCHED);
    }

    @Test
    void humanReviewContractRequiresHumanReview() {
        AiConsumerPolicyResult result = evaluate(humanReviewContract(), AiConsumerIdentity.laboratory());

        assertThat(result.decision()).isEqualTo(AiConsumerPolicyDecision.HUMAN_REVIEW_REQUIRED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerPolicyReasonCodes.CONTRACT_REQUIRES_HUMAN_REVIEW);
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerDispatchStatus.NOT_DISPATCHED);
    }

    @Test
    void notEligibleContractIsRejected() {
        AiConsumerPolicyResult result = evaluate(notEligibleContract(), AiConsumerIdentity.laboratory());

        assertThat(result.decision()).isEqualTo(AiConsumerPolicyDecision.REJECTED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerPolicyReasonCodes.CONTRACT_NOT_ELIGIBLE);
    }

    @Test
    void prematureModelAuthorizationIsRejected() {
        assertThatThrownBy(() -> new AiConsumerContract(
                        "v1",
                        lab.healthcare.fhir.aiconsumer.AiConsumerContractStatus.READY,
                        AiConsumerDispatchStatus.NOT_DISPATCHED,
                        PipelineStageStatus.SUCCESS,
                        true,
                        AgentDecision.READY,
                        FirstAiComponentStatus.PREPARED,
                        lab.healthcare.fhir.aigateway.AiExecutionStatus.ELIGIBLE_BUT_NOT_AUTHORIZED,
                        true,
                        false,
                        true,
                        FirstAiProcessingStatus.NOT_EXECUTED,
                        List.of(),
                        List.of(),
                        "NOT_REQUESTED",
                        true,
                        true,
                        "epic-sandbox",
                        "corr-062"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage(AiConsumerReasonCodes.PREMATURE_MODEL_AUTHORIZATION);
    }

    @Test
    void dispatchRequestIsRejected() {
        AiConsumerPolicyResult result = evaluate(readyContract(), laboratory(true, true, true, "v1",
                AiConsumerPolicyOperations.DISPATCH_TO_AI_SERVICE, AiConsumerPolicyScopes.CONTRACT_READ));

        assertThat(result.decision()).isEqualTo(AiConsumerPolicyDecision.REJECTED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerPolicyReasonCodes.DISPATCH_NOT_SUPPORTED);
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerDispatchStatus.NOT_DISPATCHED);
    }

    @Test
    void invalidInputIsRejected() {
        AiConsumerPolicyResult result = AiConsumerPolicy.evaluate(null);

        assertThat(result.decision()).isEqualTo(AiConsumerPolicyDecision.REJECTED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerPolicyReasonCodes.INVALID_POLICY_INPUT);
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.requiresHumanReview()).isTrue();
    }

    @Test
    void missingConsumerIdentityIsRejected() {
        AiConsumerPolicyResult result = evaluate(
                readyContract(),
                new AiConsumerIdentity(
                        "",
                        "",
                        "v1",
                        AiConsumerPolicyOperations.READ_CONTRACT,
                        AiConsumerPolicyScopes.CONTRACT_READ,
                        true,
                        true,
                        true));

        assertThat(result.decision()).isEqualTo(AiConsumerPolicyDecision.REJECTED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerPolicyReasonCodes.INVALID_POLICY_INPUT);
    }

    private static AiConsumerPolicyResult evaluate(AiConsumerContract contract, AiConsumerIdentity consumer) {
        return AiConsumerPolicy.evaluate(AiConsumerPolicyInput.of(contract, consumer));
    }

    private static AiConsumerIdentity laboratory(
            boolean authenticated,
            boolean authorized,
            boolean tenant,
            String version,
            String operation,
            String scope) {
        return new AiConsumerIdentity("lab-consumer", "LAB", version, operation, scope, tenant, authenticated, authorized);
    }

    private static AiConsumerContract readyContract() {
        return prepare(completeEpic());
    }

    private static AiConsumerContract blockedContract() {
        return prepare(new ModelBoundaryContract(
                "v2",
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                null,
                null,
                null,
                null,
                null));
    }

    private static AiConsumerContract humanReviewContract() {
        return prepare(emptyClinicalData());
    }

    private static AiConsumerContract notEligibleContract() {
        return AiConsumerContractService.prepare(AiExecutionGate.evaluate(new AiExecutionInput(
                AgentDecision.READY,
                PipelineStageStatus.SUCCESS,
                false,
                FirstAiComponentStatus.PREPARED,
                FirstAiProcessingStatus.NOT_EXECUTED,
                true,
                false,
                false,
                "INSUFFICIENT_CLINICAL_DATA",
                List.of(),
                "NOT_REQUESTED",
                true,
                true,
                "epic-sandbox",
                "corr-lab")));
    }

    private static AiConsumerContract prepare(ModelBoundaryContract contract) {
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(contract);
        DeterministicAgentResult agent = DeterministicAgent.evaluate(DeterministicAgentInput.of(contract, diagnosis));
        FirstAiResult firstAi = FirstAiComponent.process(
                AiBoundaryService.prepare(AiBoundaryInput.of(contract, diagnosis, agent), "corr-lab"));
        return AiConsumerContractService.prepare(AiExecutionGate.evaluate(firstAi));
    }

    private static ModelBoundaryContract completeEpic() {
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                collection(new BoundaryCondition("Condition", "active")),
                collection(new BoundaryObservation("Observation", "final")),
                collection(new BoundaryDiagnosticReport("DiagnosticReport", "final")),
                null);
    }

    private static ModelBoundaryContract emptyClinicalData() {
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "oracle-health-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                new BoundaryCollection<>(ClinicalSnapshotResourceStatus.SUCCESS, 0, 0, false, List.of()),
                new BoundaryCollection<>(ClinicalSnapshotResourceStatus.SUCCESS, 0, 0, false, List.of()),
                new BoundaryCollection<>(ClinicalSnapshotResourceStatus.SUCCESS, 0, 0, false, List.of()),
                new BoundaryCollection<>(ClinicalSnapshotResourceStatus.SUCCESS, 0, 0, false, List.of()));
    }

    private static <T> BoundaryCollection<T> collection(T record) {
        return new BoundaryCollection<>(ClinicalSnapshotResourceStatus.SUCCESS, 1, 1, false, List.of(record));
    }
}
