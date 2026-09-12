package lab.healthcare.fhir.aiconsumerreadiness;

import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
import lab.healthcare.fhir.aiconsumer.AiConsumerContract;
import lab.healthcare.fhir.aiconsumer.AiConsumerContractService;
import lab.healthcare.fhir.aiconsumer.AiConsumerDispatchStatus;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerIdentity;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicy;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyDecision;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyInput;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyOperations;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyResult;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyScopes;
import lab.healthcare.fhir.aigateway.AiExecutionGate;
import lab.healthcare.fhir.firstai.FirstAiComponent;
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
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AiConsumerReadinessTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T22:00:00Z");

    @Test
    void allowedPolicyIsReadyForFutureHandoffWithoutAuthorizingIt() {
        AiConsumerReadinessResult result = AiConsumerReadiness.evaluate(allowedPolicy());

        assertThat(result.readinessStatus()).isEqualTo(AiConsumerReadinessStatus.READY_FOR_FUTURE_HANDOFF);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerReadinessReasonCodes.READY_FOR_FUTURE_HANDOFF);
        assertThat(result.policyDecision()).isEqualTo(AiConsumerPolicyDecision.ALLOWED_FOR_FUTURE_CONSUMPTION);
        assertSafeInvariants(result);
    }

    @Test
    void rejectedPolicyIsBlocked() {
        AiConsumerReadinessResult result = AiConsumerReadiness.evaluate(rejectedPolicy());

        assertThat(result.readinessStatus()).isEqualTo(AiConsumerReadinessStatus.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerReadinessReasonCodes.POLICY_REJECTED);
        assertSafeInvariants(result);
    }

    @Test
    void humanReviewPolicyStaysHumanReviewRequired() {
        AiConsumerReadinessResult result = AiConsumerReadiness.evaluate(humanReviewPolicy());

        assertThat(result.readinessStatus()).isEqualTo(AiConsumerReadinessStatus.HUMAN_REVIEW_REQUIRED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerReadinessReasonCodes.POLICY_REQUIRES_HUMAN_REVIEW);
        assertThat(result.readinessStatus()).isNotEqualTo(AiConsumerReadinessStatus.READY_FOR_FUTURE_HANDOFF);
        assertSafeInvariants(result);
    }

    @Test
    void missingPolicyIsNotReady() {
        AiConsumerReadinessResult result = AiConsumerReadiness.evaluate((AiConsumerPolicyResult) null);

        assertThat(result.readinessStatus()).isEqualTo(AiConsumerReadinessStatus.NOT_READY);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerReadinessReasonCodes.POLICY_RESULT_MISSING);
        assertSafeInvariants(result);
    }

    @Test
    void prematureModelAuthorizationIsBlocked() {
        AiConsumerReadinessResult result = evaluate(allowedInput().withModelCallAuthorized(true));

        assertThat(result.readinessStatus()).isEqualTo(AiConsumerReadinessStatus.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerReadinessReasonCodes.INCONSISTENT_EXECUTION_STATE);
        assertSafeInvariants(result);
    }

    @Test
    void modelAlreadyCalledIsBlocked() {
        AiConsumerReadinessResult result = evaluate(allowedInput().withModelCalled(true));

        assertThat(result.readinessStatus()).isEqualTo(AiConsumerReadinessStatus.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerReadinessReasonCodes.INCONSISTENT_EXECUTION_STATE);
        assertSafeInvariants(result);
    }

    @Test
    void processingAlreadyExecutedIsBlocked() {
        AiConsumerReadinessResult result = evaluate(allowedInput().withProcessingStatus("EXECUTED"));

        assertThat(result.readinessStatus()).isEqualTo(AiConsumerReadinessStatus.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerReadinessReasonCodes.INCONSISTENT_EXECUTION_STATE);
        assertSafeInvariants(result);
    }

    @Test
    void dispatchAlreadyPerformedIsBlocked() {
        AiConsumerReadinessResult result = evaluate(allowedInput().withDispatchStatus("DISPATCHED"));

        assertThat(result.readinessStatus()).isEqualTo(AiConsumerReadinessStatus.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerReadinessReasonCodes.INCONSISTENT_EXECUTION_STATE);
        assertSafeInvariants(result);
    }

    @Test
    void missingHumanReviewFlagRequiresHumanReview() {
        AiConsumerReadinessResult result = evaluate(allowedInput().withRequiresHumanReview(false));

        assertThat(result.readinessStatus()).isEqualTo(AiConsumerReadinessStatus.HUMAN_REVIEW_REQUIRED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerReadinessReasonCodes.HUMAN_REVIEW_FLAG_MISSING);
        assertThat(result.readinessStatus()).isNotEqualTo(AiConsumerReadinessStatus.READY_FOR_FUTURE_HANDOFF);
        assertSafeInvariants(result);
    }

    @Test
    void unsupportedContractVersionIsBlocked() {
        AiConsumerReadinessResult result = evaluate(allowedInput().withContractVersion("v2"));

        assertThat(result.readinessStatus()).isEqualTo(AiConsumerReadinessStatus.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerReadinessReasonCodes.CONTRACT_VERSION_NOT_SUPPORTED);
        assertSafeInvariants(result);
    }

    @Test
    void unsupportedOperationIsBlocked() {
        AiConsumerReadinessResult result = evaluate(
                allowedInput().withRequestedOperation(AiConsumerPolicyOperations.EXECUTE_MODEL));

        assertThat(result.readinessStatus()).isEqualTo(AiConsumerReadinessStatus.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerReadinessReasonCodes.OPERATION_NOT_SUPPORTED_FOR_READINESS);
        assertSafeInvariants(result);
    }

    @Test
    void unsupportedScopeIsBlocked() {
        AiConsumerReadinessResult result = evaluate(allowedInput().withRequestedScope("ai.model.execute"));

        assertThat(result.readinessStatus()).isEqualTo(AiConsumerReadinessStatus.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AiConsumerReadinessReasonCodes.SCOPE_NOT_SUPPORTED_FOR_READINESS);
        assertSafeInvariants(result);
    }

    @Test
    void resultConstructorRejectsHandoffAuthorization() {
        assertThatThrownBy(() -> new AiConsumerReadinessResult(
                AiConsumerReadinessStatus.READY_FOR_FUTURE_HANDOFF,
                AiConsumerReadinessReasonCodes.READY_FOR_FUTURE_HANDOFF,
                AiConsumerPolicyDecision.ALLOWED_FOR_FUTURE_CONSUMPTION,
                "v1",
                AiConsumerPolicyOperations.READ_CONTRACT,
                AiConsumerPolicyScopes.CONTRACT_READ,
                "LAB",
                false,
                false,
                FirstAiProcessingStatus.NOT_EXECUTED,
                AiConsumerDispatchStatus.NOT_DISPATCHED,
                true,
                true,
                false))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("must not authorize handoff");
    }

    @Test
    void resultConstructorRejectsDispatchPerformed() {
        assertThatThrownBy(() -> new AiConsumerReadinessResult(
                AiConsumerReadinessStatus.READY_FOR_FUTURE_HANDOFF,
                AiConsumerReadinessReasonCodes.READY_FOR_FUTURE_HANDOFF,
                AiConsumerPolicyDecision.ALLOWED_FOR_FUTURE_CONSUMPTION,
                "v1",
                AiConsumerPolicyOperations.READ_CONTRACT,
                AiConsumerPolicyScopes.CONTRACT_READ,
                "LAB",
                false,
                false,
                FirstAiProcessingStatus.NOT_EXECUTED,
                AiConsumerDispatchStatus.NOT_DISPATCHED,
                true,
                false,
                true))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("must not perform dispatch");
    }

    private static void assertSafeInvariants(AiConsumerReadinessResult result) {
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.processingStatus()).isEqualTo(FirstAiProcessingStatus.NOT_EXECUTED);
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerDispatchStatus.NOT_DISPATCHED);
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.handoffAuthorized()).isFalse();
        assertThat(result.dispatchPerformed()).isFalse();
    }

    private static MutableInput allowedInput() {
        return MutableInput.from(allowedPolicy());
    }

    private static AiConsumerPolicyResult allowedPolicy() {
        return AiConsumerPolicy.evaluate(AiConsumerPolicyInput.of(readyContract(), AiConsumerIdentity.laboratory()));
    }

    private static AiConsumerPolicyResult rejectedPolicy() {
        return AiConsumerPolicy.evaluate(AiConsumerPolicyInput.of(
                readyContract(),
                new AiConsumerIdentity(
                        "lab-consumer",
                        "LAB",
                        "v1",
                        AiConsumerPolicyOperations.READ_CONTRACT,
                        AiConsumerPolicyScopes.CONTRACT_READ,
                        true,
                        false,
                        true)));
    }

    private static AiConsumerPolicyResult humanReviewPolicy() {
        return AiConsumerPolicy.evaluate(AiConsumerPolicyInput.of(humanReviewContract(), AiConsumerIdentity.laboratory()));
    }

    private static AiConsumerContract readyContract() {
        return prepare(completeEpic());
    }

    private static AiConsumerContract humanReviewContract() {
        return prepare(emptyClinicalData());
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

    private record MutableInput(
            AiConsumerPolicyDecision policyDecision,
            String contractVersion,
            String consumerType,
            String requestedOperation,
            String requestedScope,
            boolean modelCallAuthorized,
            boolean modelCalled,
            String processingStatus,
            String dispatchStatus,
            boolean requiresHumanReview) {

        static MutableInput from(AiConsumerPolicyResult policy) {
            return new MutableInput(
                    policy.decision(),
                    policy.contractVersion(),
                    policy.consumerType(),
                    policy.requestedOperation(),
                    policy.requestedScope(),
                    policy.modelCallAuthorized(),
                    policy.modelCalled(),
                    policy.processingStatus().name(),
                    policy.dispatchStatus().name(),
                    policy.requiresHumanReview());
        }

        MutableInput withModelCallAuthorized(boolean value) {
            return new MutableInput(
                    policyDecision,
                    contractVersion,
                    consumerType,
                    requestedOperation,
                    requestedScope,
                    value,
                    modelCalled,
                    processingStatus,
                    dispatchStatus,
                    requiresHumanReview);
        }

        MutableInput withModelCalled(boolean value) {
            return new MutableInput(
                    policyDecision,
                    contractVersion,
                    consumerType,
                    requestedOperation,
                    requestedScope,
                    modelCallAuthorized,
                    value,
                    processingStatus,
                    dispatchStatus,
                    requiresHumanReview);
        }

        MutableInput withProcessingStatus(String value) {
            return new MutableInput(
                    policyDecision,
                    contractVersion,
                    consumerType,
                    requestedOperation,
                    requestedScope,
                    modelCallAuthorized,
                    modelCalled,
                    value,
                    dispatchStatus,
                    requiresHumanReview);
        }

        MutableInput withDispatchStatus(String value) {
            return new MutableInput(
                    policyDecision,
                    contractVersion,
                    consumerType,
                    requestedOperation,
                    requestedScope,
                    modelCallAuthorized,
                    modelCalled,
                    processingStatus,
                    value,
                    requiresHumanReview);
        }

        MutableInput withRequiresHumanReview(boolean value) {
            return new MutableInput(
                    policyDecision,
                    contractVersion,
                    consumerType,
                    requestedOperation,
                    requestedScope,
                    modelCallAuthorized,
                    modelCalled,
                    processingStatus,
                    dispatchStatus,
                    value);
        }

        MutableInput withContractVersion(String value) {
            return new MutableInput(
                    policyDecision,
                    value,
                    consumerType,
                    requestedOperation,
                    requestedScope,
                    modelCallAuthorized,
                    modelCalled,
                    processingStatus,
                    dispatchStatus,
                    requiresHumanReview);
        }

        MutableInput withRequestedOperation(String value) {
            return new MutableInput(
                    policyDecision,
                    contractVersion,
                    consumerType,
                    value,
                    requestedScope,
                    modelCallAuthorized,
                    modelCalled,
                    processingStatus,
                    dispatchStatus,
                    requiresHumanReview);
        }

        MutableInput withRequestedScope(String value) {
            return new MutableInput(
                    policyDecision,
                    contractVersion,
                    consumerType,
                    requestedOperation,
                    value,
                    modelCallAuthorized,
                    modelCalled,
                    processingStatus,
                    dispatchStatus,
                    requiresHumanReview);
        }

        AiConsumerReadinessInput toInput() {
            return new AiConsumerReadinessInput(
                    policyDecision,
                    contractVersion,
                    consumerType,
                    requestedOperation,
                    requestedScope,
                    modelCallAuthorized,
                    modelCalled,
                    processingStatus,
                    dispatchStatus,
                    requiresHumanReview);
        }
    }

    private static AiConsumerReadinessResult evaluate(MutableInput input) {
        return AiConsumerReadiness.evaluate(input.toInput());
    }
}
