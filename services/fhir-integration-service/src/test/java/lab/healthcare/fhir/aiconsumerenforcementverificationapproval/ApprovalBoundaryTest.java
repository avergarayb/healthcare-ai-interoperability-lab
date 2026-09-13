package lab.healthcare.fhir.aiconsumerenforcementverificationapproval;

import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
import lab.healthcare.fhir.aiconsumer.AiConsumerContract;
import lab.healthcare.fhir.aiconsumer.AiConsumerContractService;
import lab.healthcare.fhir.aiconsumeraccess.AiConsumerClinicalDataAccessBoundary;
import lab.healthcare.fhir.aiconsumerauthorization.AiConsumerAuthorizationBoundary;
import lab.healthcare.fhir.aiconsumerconsent.AiConsumerConsentBoundary;
import lab.healthcare.fhir.aiconsumerenforcement.AiConsumerClinicalDataEnforcementBoundary;
import lab.healthcare.fhir.aiconsumerenforcementexecution.AiConsumerClinicalDataEnforcementExecutionBoundary;
import lab.healthcare.fhir.aiconsumerenforcementverification.AiConsumerClinicalDataEnforcementExecutionVerificationBoundary;
import lab.healthcare.fhir.aiconsumerenforcementverificationdecision.AiConsumerVerificationDecisionBoundary;
import lab.healthcare.fhir.aiconsumerenforcementverificationdecision.AiConsumerVerificationDecisionResult;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerIdentity;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicy;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyInput;
import lab.healthcare.fhir.aiconsumerreadiness.AiConsumerReadiness;
import lab.healthcare.fhir.aiconsumerscope.AiConsumerDataScopeBoundary;
import lab.healthcare.fhir.aihandoffauthorization.AiHandoffAuthorizationBoundary;
import lab.healthcare.fhir.aigateway.AiExecutionGate;
import lab.healthcare.fhir.firstai.FirstAiComponent;
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

class ApprovalBoundaryTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-13T00:30:00Z");

    @Test
    void liveDecisionWithoutApprovalProviderIsNotAvailable() {
        AiConsumerEnforcementVerificationApprovalResult result =
                AiConsumerEnforcementVerificationApprovalBoundary.evaluate(validDecision());

        assertThat(result.status())
                .isEqualTo(AiConsumerEnforcementVerificationApprovalStatus.VERIFICATION_APPROVAL_NOT_AVAILABLE);
        assertThat(result.verificationApprovalAvailable()).isFalse();
        assertThat(result.verificationApproved()).isFalse();
        assertThat(result.requiresHumanReview()).isTrue();
        assertSafeInvariants(result);
    }

    @Test
    void missingDecisionResultIsBlocked() {
        AiConsumerEnforcementVerificationApprovalResult result =
                AiConsumerEnforcementVerificationApprovalBoundary.evaluate(
                        (AiConsumerVerificationDecisionResult) null);

        assertThat(result.status()).isEqualTo(AiConsumerEnforcementVerificationApprovalStatus.BLOCKED);
        assertThat(result.reason())
                .isEqualTo(AiConsumerEnforcementVerificationApprovalReasonCodes
                        .VERIFICATION_DECISION_RESULT_MISSING);
        assertSafeInvariants(result);
    }

    @Test
    void missingContextIsBlocked() {
        AiConsumerEnforcementVerificationApprovalResult result =
                AiConsumerEnforcementVerificationApprovalBoundary.evaluate(validDecision(), null);

        assertThat(result.status()).isEqualTo(AiConsumerEnforcementVerificationApprovalStatus.BLOCKED);
        assertThat(result.reason())
                .isEqualTo(AiConsumerEnforcementVerificationApprovalReasonCodes
                        .VERIFICATION_APPROVAL_CONTEXT_MISSING);
        assertSafeInvariants(result);
    }

    @Test
    void unavailablePreviousDecisionStaysNotApproved() {
        AiConsumerVerificationDecisionResult decision = validDecision();
        assertThat(decision.verificationDecisionAvailable()).isFalse();

        AiConsumerEnforcementVerificationApprovalResult result =
                AiConsumerEnforcementVerificationApprovalBoundary.evaluate(
                        decision,
                        ClinicalDataEnforcementVerificationApprovalContext.laboratory()
                                .withDecisionAvailabilityCheckAttempted(true));

        assertThat(result.status()).isEqualTo(AiConsumerEnforcementVerificationApprovalStatus.BLOCKED);
        assertThat(result.reason())
                .isEqualTo(AiConsumerEnforcementVerificationApprovalReasonCodes.VERIFICATION_DECISION_NOT_AVAILABLE);
        assertThat(result.verificationApproved()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void unevaluatedPreviousDecisionStaysNotApproved() {
        AiConsumerVerificationDecisionResult decision = validDecision();
        assertThat(decision.verificationDecisionEvaluated()).isFalse();

        AiConsumerEnforcementVerificationApprovalResult result =
                AiConsumerEnforcementVerificationApprovalBoundary.evaluate(
                        decision,
                        ClinicalDataEnforcementVerificationApprovalContext.laboratory()
                                .withDecisionEvaluatedCheckAttempted(true));

        assertThat(result.status()).isEqualTo(AiConsumerEnforcementVerificationApprovalStatus.BLOCKED);
        assertThat(result.reason())
                .isEqualTo(AiConsumerEnforcementVerificationApprovalReasonCodes.VERIFICATION_DECISION_NOT_EVALUATED);
        assertSafeInvariants(result);
    }

    @Test
    void inheritedHumanReviewStaysRequired() {
        AiConsumerVerificationDecisionResult decision = validDecision();
        assertThat(decision.requiresHumanReview()).isTrue();

        AiConsumerEnforcementVerificationApprovalResult result =
                AiConsumerEnforcementVerificationApprovalBoundary.evaluate(
                        decision,
                        ClinicalDataEnforcementVerificationApprovalContext.laboratory()
                                .withApprovalHumanReviewRequired(true));

        assertThat(result.status())
                .isEqualTo(AiConsumerEnforcementVerificationApprovalStatus.HUMAN_REVIEW_REQUIRED);
        assertThat(result.reason())
                .isEqualTo(AiConsumerEnforcementVerificationApprovalReasonCodes
                        .HUMAN_REVIEW_REQUIRED_BY_PREVIOUS_BOUNDARY);
        assertThat(result.requiresHumanReview()).isTrue();
        assertSafeInvariants(result);
    }

    @Test
    void syntheticApprovalClaimsRequireHumanReview() {
        AiConsumerEnforcementVerificationApprovalResult result =
                AiConsumerEnforcementVerificationApprovalBoundary.evaluate(
                        validDecision(),
                        ClinicalDataEnforcementVerificationApprovalContext.laboratory().withPositiveClaims());

        assertThat(result.status())
                .isEqualTo(AiConsumerEnforcementVerificationApprovalStatus.HUMAN_REVIEW_REQUIRED);
        assertThat(result.reason())
                .isEqualTo(AiConsumerEnforcementVerificationApprovalReasonCodes.SYNTHETIC_APPROVAL_CLAIMS_UNTRUSTED);
        assertThat(result.verificationApproved()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void syntheticEvidenceClaimsAreNotApproval() {
        AiConsumerEnforcementVerificationApprovalResult result =
                AiConsumerEnforcementVerificationApprovalBoundary.evaluate(
                        validDecision(),
                        ClinicalDataEnforcementVerificationApprovalContext.laboratory().withEvidenceClaims());

        assertThat(result.status())
                .isEqualTo(AiConsumerEnforcementVerificationApprovalStatus.HUMAN_REVIEW_REQUIRED);
        assertThat(result.approvalEvidenceEvaluated()).isFalse();
        assertThat(result.verificationApproved()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void syntheticPolicyClaimsAreNotApproval() {
        AiConsumerEnforcementVerificationApprovalResult result =
                AiConsumerEnforcementVerificationApprovalBoundary.evaluate(
                        validDecision(),
                        ClinicalDataEnforcementVerificationApprovalContext.laboratory().withPolicyClaims());

        assertThat(result.status())
                .isEqualTo(AiConsumerEnforcementVerificationApprovalStatus.HUMAN_REVIEW_REQUIRED);
        assertThat(result.approvalPolicyEvaluated()).isFalse();
        assertThat(result.verificationApproved()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void claimedApprovalCannotManufactureGrant() {
        AiConsumerEnforcementVerificationApprovalResult result =
                AiConsumerEnforcementVerificationApprovalBoundary.evaluate(
                        AiConsumerEnforcementVerificationApprovalInput.from(validDecision())
                                .withVerificationApproved(true));

        assertThat(result.status())
                .isEqualTo(AiConsumerEnforcementVerificationApprovalStatus.HUMAN_REVIEW_REQUIRED);
        assertThat(result.verificationApproved()).isFalse();
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void constructorRejectsApprovedAndGrantFlags() {
        AiConsumerEnforcementVerificationApprovalResult safe =
                AiConsumerEnforcementVerificationApprovalResult.denied(
                        AiConsumerEnforcementVerificationApprovalStatus.VERIFICATION_APPROVAL_NOT_AVAILABLE,
                        AiConsumerEnforcementVerificationApprovalReasonCodes.VERIFICATION_APPROVAL_NOT_AVAILABLE,
                        true,
                        ClinicalDataEnforcementVerificationApprovalContext.SOURCE_LABORATORY);
        assertThatThrownBy(() -> copyWith(safe, true, false, false))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> copyWith(safe, false, true, false))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> copyWith(safe, false, false, true))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void evaluationIsDeterministicAndHasNoClinicalPayload() {
        AiConsumerEnforcementVerificationApprovalResult first =
                AiConsumerEnforcementVerificationApprovalBoundary.evaluate(validDecision());
        AiConsumerEnforcementVerificationApprovalResult second =
                AiConsumerEnforcementVerificationApprovalBoundary.evaluate(validDecision());

        assertThat(first).isEqualTo(second);
        assertThat(first.toString()).doesNotContain("access_token");
        assertThat(first.toString()).doesNotContain("Patient/");
        assertThat(first.toString()).doesNotContain("HTTP 200");
        assertSafeInvariants(first);
    }

    private static AiConsumerEnforcementVerificationApprovalResult copyWith(
            AiConsumerEnforcementVerificationApprovalResult source,
            boolean verificationApproved,
            boolean clinicalDataAccessGranted,
            boolean executionVerified) {
        return new AiConsumerEnforcementVerificationApprovalResult(
                source.boundaryVersion(),
                source.status(),
                source.reason(),
                source.operation(),
                source.inputAvailable(),
                source.requestSource(),
                source.approvalEvaluationStatus(),
                source.decisionReason(),
                source.verificationApprovalAvailable(),
                source.verificationApprovalEvaluated(),
                source.approvalEvidenceEvaluated(),
                source.approvalPolicyEvaluated(),
                source.approvalHumanReviewRequired(),
                source.decisionAvailable(),
                source.decisionEvaluated(),
                source.verificationInputAccepted(),
                source.verificationEvidenceAccepted(),
                source.verificationDecisionProviderConfigured(),
                verificationApproved,
                source.verificationDecisionAvailable(),
                source.verificationDecisionEvaluated(),
                source.executionEvidenceAvailable(),
                source.executionEvidenceEvaluated(),
                source.executionVerificationAvailable(),
                source.executionVerificationProviderConfigured(),
                executionVerified,
                source.executionDecisionAvailable(),
                source.executionDecisionEvaluated(),
                source.enforcementExecutionAvailable(),
                source.enforcementExecutionProviderConfigured(),
                source.enforcementExecutionPerformed(),
                source.realAuthorizationRequired(),
                clinicalDataAccessGranted,
                source.clinicalDataAccessAllowed(),
                source.clinicalDataAccessEnforced(),
                source.enforcementDecisionAvailable(),
                source.enforcementDecisionEvaluated(),
                source.clinicalDataAccessEnforcementAvailable(),
                source.clinicalDataAccessEnforcementProviderConfigured(),
                source.clinicalDataAccessEnforcementExecuted(),
                source.accessRequestEvaluated(),
                source.clinicalDataAccessRequested(),
                source.clinicalDataAccessGrantAvailable(),
                source.clinicalDataAccessProviderConfigured(),
                source.clinicalDataAccessAuthorizationAvailable(),
                source.scopeEvaluated(),
                source.minimizationEvaluated(),
                source.purposeScopeAlignmentEvaluated(),
                source.clinicalDataScopeProviderConfigured(),
                source.clinicalDataScopeApprovalAvailable(),
                source.consentVerified(),
                source.purposeApproved(),
                source.dataScopeApproved(),
                source.consentProviderConfigured(),
                source.consentAvailable(),
                source.authenticationVerified(),
                source.authorizationGranted(),
                source.realSecurityProviderConfigured(),
                source.consumerAuthorizationAvailable(),
                source.handoffAuthorized(),
                source.dispatchPerformed(),
                source.externalAuthorizationAvailable(),
                source.modelCallAuthorized(),
                source.modelCalled(),
                source.processingStatus(),
                source.dispatchStatus(),
                source.requiresHumanReview());
    }

    private static void assertSafeInvariants(AiConsumerEnforcementVerificationApprovalResult result) {
        assertThat(result.verificationApprovalAvailable()).isFalse();
        assertThat(result.verificationApprovalEvaluated()).isFalse();
        assertThat(result.verificationApproved()).isFalse();
        assertThat(result.approvalEvidenceEvaluated()).isFalse();
        assertThat(result.approvalPolicyEvaluated()).isFalse();
        assertThat(result.approvalHumanReviewRequired()).isTrue();
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertThat(result.clinicalDataAccessAllowed()).isFalse();
        assertThat(result.clinicalDataAccessRequested()).isFalse();
        assertThat(result.clinicalDataAccessEnforced()).isFalse();
        assertThat(result.enforcementExecutionPerformed()).isFalse();
        assertThat(result.executionVerified()).isFalse();
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.processingStatus()).isEqualTo(AiConsumerEnforcementVerificationApprovalResult.NOT_EXECUTED);
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerEnforcementVerificationApprovalResult.NOT_DISPATCHED);
    }

    private static AiConsumerVerificationDecisionResult validDecision() {
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(completeEpic());
        DeterministicAgentResult agent =
                DeterministicAgent.evaluate(DeterministicAgentInput.of(completeEpic(), diagnosis));
        FirstAiResult firstAi = FirstAiComponent.process(
                AiBoundaryService.prepare(AiBoundaryInput.of(completeEpic(), diagnosis, agent), "corr-lab"));
        AiConsumerContract contract = AiConsumerContractService.prepare(AiExecutionGate.evaluate(firstAi));
        return AiConsumerVerificationDecisionBoundary.evaluate(
                AiConsumerClinicalDataEnforcementExecutionVerificationBoundary.evaluate(
                        AiConsumerClinicalDataEnforcementExecutionBoundary.evaluate(
                                AiConsumerClinicalDataEnforcementBoundary.evaluate(
                                        AiConsumerClinicalDataAccessBoundary.evaluate(
                                                AiConsumerDataScopeBoundary.evaluate(
                                                        AiConsumerConsentBoundary.evaluate(
                                                                AiConsumerAuthorizationBoundary.evaluate(
                                                                        AiHandoffAuthorizationBoundary.evaluate(
                                                                                AiConsumerReadiness.evaluate(
                                                                                        AiConsumerPolicy.evaluate(
                                                                                                AiConsumerPolicyInput
                                                                                                        .of(
                                                                                                                contract,
                                                                                                                AiConsumerIdentity
                                                                                                                        .laboratory()))))))))))));
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

    private static <T> BoundaryCollection<T> collection(T record) {
        return new BoundaryCollection<>(ClinicalSnapshotResourceStatus.SUCCESS, 1, 1, false, List.of(record));
    }
}
