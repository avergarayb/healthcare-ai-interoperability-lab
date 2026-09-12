package lab.healthcare.fhir.aihandoffauthorization;

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
import lab.healthcare.fhir.aiconsumerreadiness.AiConsumerReadiness;
import lab.healthcare.fhir.aiconsumerreadiness.AiConsumerReadinessResult;
import lab.healthcare.fhir.aiconsumerreadiness.AiConsumerReadinessStatus;
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

class AiHandoffAuthorizationBoundaryTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T22:00:00Z");

    @Test
    void readyReadinessIsStillNotAuthorized() {
        AiHandoffAuthorizationResult result = AiHandoffAuthorizationBoundary.evaluate(readyReadiness());

        assertThat(result.authorizationStatus()).isEqualTo(AiHandoffAuthorizationStatus.HANDOFF_NOT_AUTHORIZED);
        assertThat(result.reasonCode()).isEqualTo(AiHandoffAuthorizationReasonCodes.REAL_AUTHORIZATION_NOT_IMPLEMENTED);
        assertThat(result.readinessStatus()).isEqualTo(AiConsumerReadinessStatus.READY_FOR_FUTURE_HANDOFF);
        assertSafeInvariants(result);
    }

    @Test
    void blockedReadinessIsBlocked() {
        AiHandoffAuthorizationResult result = AiHandoffAuthorizationBoundary.evaluate(blockedReadiness());

        assertThat(result.authorizationStatus()).isEqualTo(AiHandoffAuthorizationStatus.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AiHandoffAuthorizationReasonCodes.READINESS_BLOCKED);
        assertSafeInvariants(result);
    }

    @Test
    void humanReviewReadinessStaysHumanReviewRequired() {
        AiHandoffAuthorizationResult result = AiHandoffAuthorizationBoundary.evaluate(humanReviewReadiness());

        assertThat(result.authorizationStatus()).isEqualTo(AiHandoffAuthorizationStatus.HUMAN_REVIEW_REQUIRED);
        assertThat(result.reasonCode()).isEqualTo(AiHandoffAuthorizationReasonCodes.READINESS_REQUIRES_HUMAN_REVIEW);
        assertSafeInvariants(result);
    }

    @Test
    void missingReadinessIsNotReadyForAuthorization() {
        AiHandoffAuthorizationResult result = AiHandoffAuthorizationBoundary.evaluate((AiConsumerReadinessResult) null);

        assertThat(result.authorizationStatus()).isEqualTo(AiHandoffAuthorizationStatus.NOT_READY_FOR_AUTHORIZATION);
        assertThat(result.reasonCode()).isEqualTo(AiHandoffAuthorizationReasonCodes.READINESS_RESULT_MISSING);
        assertSafeInvariants(result);
    }

    @Test
    void prematureModelAuthorizationIsBlocked() {
        AiHandoffAuthorizationResult result = evaluate(readyInput().withModelCallAuthorized(true));

        assertThat(result.authorizationStatus()).isEqualTo(AiHandoffAuthorizationStatus.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AiHandoffAuthorizationReasonCodes.INCONSISTENT_EXECUTION_STATE);
        assertSafeInvariants(result);
    }

    @Test
    void modelAlreadyCalledIsBlocked() {
        AiHandoffAuthorizationResult result = evaluate(readyInput().withModelCalled(true));

        assertThat(result.authorizationStatus()).isEqualTo(AiHandoffAuthorizationStatus.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AiHandoffAuthorizationReasonCodes.INCONSISTENT_EXECUTION_STATE);
        assertSafeInvariants(result);
    }

    @Test
    void dispatchAlreadyPerformedIsBlocked() {
        AiHandoffAuthorizationResult result = evaluate(readyInput().withDispatchStatus("DISPATCHED"));

        assertThat(result.authorizationStatus()).isEqualTo(AiHandoffAuthorizationStatus.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AiHandoffAuthorizationReasonCodes.INCONSISTENT_EXECUTION_STATE);
        assertSafeInvariants(result);
    }

    @Test
    void handoffAlreadyMarkedAuthorizedIsBlockedAndNotPropagated() {
        AiHandoffAuthorizationResult result = evaluate(readyInput().withHandoffAuthorized(true));

        assertThat(result.authorizationStatus()).isEqualTo(AiHandoffAuthorizationStatus.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AiHandoffAuthorizationReasonCodes.INCONSISTENT_EXECUTION_STATE);
        assertThat(result.handoffAuthorized()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void missingHumanReviewFlagRequiresHumanReview() {
        AiHandoffAuthorizationResult result = evaluate(readyInput().withRequiresHumanReview(false));

        assertThat(result.authorizationStatus()).isEqualTo(AiHandoffAuthorizationStatus.HUMAN_REVIEW_REQUIRED);
        assertThat(result.reasonCode()).isEqualTo(AiHandoffAuthorizationReasonCodes.HUMAN_REVIEW_FLAG_MISSING);
        assertSafeInvariants(result);
    }

    @Test
    void conceptualHandoffScopeIsNotGranted() {
        AiHandoffAuthorizationResult result =
                evaluate(readyInput().withRequestedHandoffScope(AiHandoffAuthorizationScopes.HANDOFF_REQUEST));

        assertThat(result.authorizationStatus()).isEqualTo(AiHandoffAuthorizationStatus.HANDOFF_NOT_AUTHORIZED);
        assertThat(result.reasonCode()).isEqualTo(AiHandoffAuthorizationReasonCodes.HANDOFF_SCOPE_NOT_GRANTED);
        assertSafeInvariants(result);
    }

    @Test
    void missingExternalAuthorizationKeepsHandoffUnauthorized() {
        AiHandoffAuthorizationResult result = evaluate(readyInput().withExternalAuthorizationAvailable(false));

        assertThat(result.authorizationStatus()).isEqualTo(AiHandoffAuthorizationStatus.HANDOFF_NOT_AUTHORIZED);
        assertThat(result.reasonCode()).isEqualTo(AiHandoffAuthorizationReasonCodes.REAL_AUTHORIZATION_NOT_IMPLEMENTED);
        assertThat(result.externalAuthorizationAvailable()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void resultConstructorRejectsHandoffAuthorization() {
        assertThatThrownBy(() -> readyResult(true, false))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("must not authorize handoff");
    }

    @Test
    void resultConstructorRejectsExternalAuthorization() {
        assertThatThrownBy(() -> new AiHandoffAuthorizationResult(
                AiHandoffAuthorizationStatus.HANDOFF_NOT_AUTHORIZED,
                AiHandoffAuthorizationReasonCodes.REAL_AUTHORIZATION_NOT_IMPLEMENTED,
                AiConsumerReadinessStatus.READY_FOR_FUTURE_HANDOFF,
                AiConsumerPolicyDecision.ALLOWED_FOR_FUTURE_CONSUMPTION,
                "v1",
                AiConsumerPolicyOperations.READ_CONTRACT,
                AiConsumerPolicyScopes.CONTRACT_READ,
                "LAB",
                true,
                true,
                true,
                true,
                true,
                false,
                false,
                false,
                false,
                FirstAiProcessingStatus.NOT_EXECUTED,
                AiConsumerDispatchStatus.NOT_DISPATCHED,
                true))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("no external authorization");
    }

    private static AiHandoffAuthorizationResult readyResult(boolean handoffAuthorized, boolean dispatchPerformed) {
        return new AiHandoffAuthorizationResult(
                AiHandoffAuthorizationStatus.HANDOFF_NOT_AUTHORIZED,
                AiHandoffAuthorizationReasonCodes.REAL_AUTHORIZATION_NOT_IMPLEMENTED,
                AiConsumerReadinessStatus.READY_FOR_FUTURE_HANDOFF,
                AiConsumerPolicyDecision.ALLOWED_FOR_FUTURE_CONSUMPTION,
                "v1",
                AiConsumerPolicyOperations.READ_CONTRACT,
                AiConsumerPolicyScopes.CONTRACT_READ,
                "LAB",
                true,
                true,
                true,
                true,
                false,
                handoffAuthorized,
                dispatchPerformed,
                false,
                false,
                FirstAiProcessingStatus.NOT_EXECUTED,
                AiConsumerDispatchStatus.NOT_DISPATCHED,
                true);
    }

    private static void assertSafeInvariants(AiHandoffAuthorizationResult result) {
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.processingStatus()).isEqualTo(FirstAiProcessingStatus.NOT_EXECUTED);
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerDispatchStatus.NOT_DISPATCHED);
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.handoffAuthorized()).isFalse();
        assertThat(result.dispatchPerformed()).isFalse();
        assertThat(result.externalAuthorizationAvailable()).isFalse();
    }

    private static MutableInput readyInput() {
        return MutableInput.from(readyReadiness());
    }

    private static AiConsumerReadinessResult readyReadiness() {
        return AiConsumerReadiness.evaluate(AiConsumerPolicy.evaluate(
                AiConsumerPolicyInput.of(readyContract(), AiConsumerIdentity.laboratory())));
    }

    private static AiConsumerReadinessResult blockedReadiness() {
        AiConsumerPolicyResult policy = AiConsumerPolicy.evaluate(AiConsumerPolicyInput.of(
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
        return AiConsumerReadiness.evaluate(policy);
    }

    private static AiConsumerReadinessResult humanReviewReadiness() {
        return AiConsumerReadiness.evaluate(AiConsumerPolicy.evaluate(
                AiConsumerPolicyInput.of(humanReviewContract(), AiConsumerIdentity.laboratory())));
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
            AiConsumerReadinessStatus readinessStatus,
            AiConsumerPolicyDecision policyDecision,
            String contractVersion,
            String requestedOperation,
            String requestedScope,
            String consumerType,
            boolean modelCallAuthorized,
            boolean modelCalled,
            String processingStatus,
            String dispatchStatus,
            boolean requiresHumanReview,
            boolean handoffAuthorized,
            boolean dispatchPerformed,
            boolean consumerIdentityPresent,
            boolean consumerAuthenticated,
            boolean consumerAuthorized,
            boolean tenantContextPresent,
            boolean externalAuthorizationAvailable,
            String requestedHandoffScope) {

        static MutableInput from(AiConsumerReadinessResult readiness) {
            AiHandoffAuthorizationInput input = AiHandoffAuthorizationInput.from(readiness);
            return new MutableInput(
                    input.readinessStatus(),
                    input.policyDecision(),
                    input.contractVersion(),
                    input.requestedOperation(),
                    input.requestedScope(),
                    input.consumerType(),
                    input.modelCallAuthorized(),
                    input.modelCalled(),
                    input.processingStatus(),
                    input.dispatchStatus(),
                    input.requiresHumanReview(),
                    input.handoffAuthorized(),
                    input.dispatchPerformed(),
                    input.consumerIdentityPresent(),
                    input.consumerAuthenticated(),
                    input.consumerAuthorized(),
                    input.tenantContextPresent(),
                    input.externalAuthorizationAvailable(),
                    input.requestedHandoffScope());
        }

        MutableInput withModelCallAuthorized(boolean value) {
            return copy(value, modelCalled, processingStatus, dispatchStatus, requiresHumanReview, handoffAuthorized,
                    dispatchPerformed, externalAuthorizationAvailable, requestedHandoffScope);
        }

        MutableInput withModelCalled(boolean value) {
            return copy(modelCallAuthorized, value, processingStatus, dispatchStatus, requiresHumanReview,
                    handoffAuthorized, dispatchPerformed, externalAuthorizationAvailable, requestedHandoffScope);
        }

        MutableInput withDispatchStatus(String value) {
            return copy(modelCallAuthorized, modelCalled, processingStatus, value, requiresHumanReview,
                    handoffAuthorized, dispatchPerformed, externalAuthorizationAvailable, requestedHandoffScope);
        }

        MutableInput withHandoffAuthorized(boolean value) {
            return copy(modelCallAuthorized, modelCalled, processingStatus, dispatchStatus, requiresHumanReview, value,
                    dispatchPerformed, externalAuthorizationAvailable, requestedHandoffScope);
        }

        MutableInput withRequiresHumanReview(boolean value) {
            return copy(modelCallAuthorized, modelCalled, processingStatus, dispatchStatus, value, handoffAuthorized,
                    dispatchPerformed, externalAuthorizationAvailable, requestedHandoffScope);
        }

        MutableInput withExternalAuthorizationAvailable(boolean value) {
            return copy(modelCallAuthorized, modelCalled, processingStatus, dispatchStatus, requiresHumanReview,
                    handoffAuthorized, dispatchPerformed, value, requestedHandoffScope);
        }

        MutableInput withRequestedHandoffScope(String value) {
            return copy(modelCallAuthorized, modelCalled, processingStatus, dispatchStatus, requiresHumanReview,
                    handoffAuthorized, dispatchPerformed, externalAuthorizationAvailable, value);
        }

        private MutableInput copy(
                boolean modelCallAuthorized,
                boolean modelCalled,
                String processingStatus,
                String dispatchStatus,
                boolean requiresHumanReview,
                boolean handoffAuthorized,
                boolean dispatchPerformed,
                boolean externalAuthorizationAvailable,
                String requestedHandoffScope) {
            return new MutableInput(
                    readinessStatus,
                    policyDecision,
                    contractVersion,
                    requestedOperation,
                    requestedScope,
                    consumerType,
                    modelCallAuthorized,
                    modelCalled,
                    processingStatus,
                    dispatchStatus,
                    requiresHumanReview,
                    handoffAuthorized,
                    dispatchPerformed,
                    consumerIdentityPresent,
                    consumerAuthenticated,
                    consumerAuthorized,
                    tenantContextPresent,
                    externalAuthorizationAvailable,
                    requestedHandoffScope);
        }

        AiHandoffAuthorizationInput toInput() {
            return new AiHandoffAuthorizationInput(
                    readinessStatus,
                    policyDecision,
                    contractVersion,
                    requestedOperation,
                    requestedScope,
                    consumerType,
                    modelCallAuthorized,
                    modelCalled,
                    processingStatus,
                    dispatchStatus,
                    requiresHumanReview,
                    handoffAuthorized,
                    dispatchPerformed,
                    consumerIdentityPresent,
                    consumerAuthenticated,
                    consumerAuthorized,
                    tenantContextPresent,
                    externalAuthorizationAvailable,
                    requestedHandoffScope);
        }
    }

    private static AiHandoffAuthorizationResult evaluate(MutableInput input) {
        return AiHandoffAuthorizationBoundary.evaluate(input.toInput());
    }
}
