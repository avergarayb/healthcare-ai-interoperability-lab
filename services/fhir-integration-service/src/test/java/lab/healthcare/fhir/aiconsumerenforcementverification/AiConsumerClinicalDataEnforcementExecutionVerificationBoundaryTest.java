package lab.healthcare.fhir.aiconsumerenforcementverification;

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
import lab.healthcare.fhir.aiconsumerenforcementexecution.AiConsumerClinicalDataEnforcementExecutionResult;
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

class AiConsumerClinicalDataEnforcementExecutionVerificationBoundaryTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T23:30:00Z");

    @Test
    void validExecutionWithoutVerificationProviderIsNotVerified() {
        AiConsumerClinicalDataEnforcementExecutionVerificationResult result =
                AiConsumerClinicalDataEnforcementExecutionVerificationBoundary.evaluate(validExecution());

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionVerificationStatus
                        .NOT_VERIFIED_FOR_CLINICAL_DATA_ACCESS);
        assertThat(result.reason())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionVerificationReasonCodes.EXECUTION_NOT_VERIFIED);
        assertThat(result.verificationDecisionAvailable()).isFalse();
        assertThat(result.executionEvidenceAvailable()).isFalse();
        assertThat(result.executionVerified()).isFalse();
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void missingExecutionResultIsNotAvailable() {
        AiConsumerClinicalDataEnforcementExecutionVerificationResult result =
                AiConsumerClinicalDataEnforcementExecutionVerificationBoundary.evaluate(
                        (AiConsumerClinicalDataEnforcementExecutionResult) null);

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionVerificationStatus
                        .VERIFICATION_INPUT_NOT_AVAILABLE);
        assertThat(result.reason())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionVerificationReasonCodes.MISSING_EXECUTION_RESULT);
        assertSafeInvariants(result);
    }

    @Test
    void executionResultCheckRequiresExecutionResult() {
        AiConsumerClinicalDataEnforcementExecutionVerificationResult result =
                AiConsumerClinicalDataEnforcementExecutionVerificationBoundary.evaluate(
                        validExecution(),
                        ClinicalDataEnforcementExecutionVerificationContext.laboratory()
                                .withExecutionResultCheckAttempted(true));

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionVerificationStatus
                        .VERIFICATION_REQUIRES_EXECUTION_RESULT);
        assertThat(result.executionVerified()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void evidenceCheckRequiresEvidence() {
        AiConsumerClinicalDataEnforcementExecutionVerificationResult result =
                AiConsumerClinicalDataEnforcementExecutionVerificationBoundary.evaluate(
                        validExecution(),
                        ClinicalDataEnforcementExecutionVerificationContext.laboratory()
                                .withEvidenceCheckAttempted(true));

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionVerificationStatus
                        .VERIFICATION_REQUIRES_EVIDENCE);
        assertThat(result.executionEvidenceAvailable()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void providerCheckRequiresRealProvider() {
        AiConsumerClinicalDataEnforcementExecutionVerificationResult result =
                AiConsumerClinicalDataEnforcementExecutionVerificationBoundary.evaluate(
                        validExecution(),
                        ClinicalDataEnforcementExecutionVerificationContext.laboratory()
                                .withProviderCheckAttempted(true));

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionVerificationStatus
                        .VERIFICATION_REQUIRES_REAL_PROVIDER);
        assertThat(result.executionVerificationProviderConfigured()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void humanReviewCheckStaysRequired() {
        AiConsumerClinicalDataEnforcementExecutionVerificationResult result =
                AiConsumerClinicalDataEnforcementExecutionVerificationBoundary.evaluate(
                        validExecution(),
                        ClinicalDataEnforcementExecutionVerificationContext.laboratory()
                                .withHumanReviewCheckAttempted(true));

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionVerificationStatus
                        .VERIFICATION_REQUIRES_HUMAN_REVIEW);
        assertThat(result.requiresHumanReview()).isTrue();
        assertSafeInvariants(result);
    }

    @Test
    void claimedExecutionIsNotVerifiedEvidence() {
        AiConsumerClinicalDataEnforcementExecutionVerificationResult result =
                AiConsumerClinicalDataEnforcementExecutionVerificationBoundary.evaluate(
                        AiConsumerClinicalDataEnforcementExecutionVerificationInput.from(validExecution())
                                .withEnforcementExecutionPerformed(true));

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionVerificationStatus.VERIFICATION_BLOCKED);
        assertThat(result.enforcementExecutionPerformed()).isFalse();
        assertThat(result.executionVerified()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void manipulatedContextCannotVerifyExecution() {
        AiConsumerClinicalDataEnforcementExecutionVerificationResult result =
                AiConsumerClinicalDataEnforcementExecutionVerificationBoundary.evaluate(
                        validExecution(),
                        ClinicalDataEnforcementExecutionVerificationContext.laboratory().withPositiveClaims());

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionVerificationStatus.VERIFICATION_BLOCKED);
        assertThat(result.reason())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionVerificationReasonCodes
                        .UNTRUSTED_VERIFICATION_ASSERTION);
        assertThat(result.executionVerified()).isFalse();
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void grantedInputFlagCannotManufacturePermission() {
        AiConsumerClinicalDataEnforcementExecutionVerificationResult result =
                AiConsumerClinicalDataEnforcementExecutionVerificationBoundary.evaluate(
                        AiConsumerClinicalDataEnforcementExecutionVerificationInput.from(validExecution())
                                .withClinicalDataAccessGranted(true));

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionVerificationStatus.VERIFICATION_BLOCKED);
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void missingTenantScopeIsBlocked() {
        AiConsumerClinicalDataEnforcementExecutionVerificationResult result =
                AiConsumerClinicalDataEnforcementExecutionVerificationBoundary.evaluate(
                        validExecution(),
                        ClinicalDataEnforcementExecutionVerificationContext.laboratory()
                                .withTenantScopePresent(false));

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionVerificationStatus.VERIFICATION_BLOCKED);
        assertThat(result.reason())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionVerificationReasonCodes.MISSING_TENANT_SCOPE);
        assertSafeInvariants(result);
    }

    @Test
    void evaluationIsDeterministicAndHasNoClinicalPayload() {
        AiConsumerClinicalDataEnforcementExecutionVerificationResult first =
                AiConsumerClinicalDataEnforcementExecutionVerificationBoundary.evaluate(validExecution());
        AiConsumerClinicalDataEnforcementExecutionVerificationResult second =
                AiConsumerClinicalDataEnforcementExecutionVerificationBoundary.evaluate(validExecution());

        assertThat(first).isEqualTo(second);
        assertThat(first.toString()).doesNotContain("access_token");
        assertThat(first.toString()).doesNotContain("Patient/");
        assertThat(first.toString()).doesNotContain("\"resourceType\"");
        assertThat(first.toString()).doesNotContain("HTTP 200");
        assertSafeInvariants(first);
    }

    private static void assertSafeInvariants(AiConsumerClinicalDataEnforcementExecutionVerificationResult result) {
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.processingStatus())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionVerificationResult.NOT_EXECUTED);
        assertThat(result.dispatchStatus())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionVerificationResult.NOT_DISPATCHED);
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.handoffAuthorized()).isFalse();
        assertThat(result.dispatchPerformed()).isFalse();
        assertThat(result.externalAuthorizationAvailable()).isFalse();
        assertThat(result.authenticationVerified()).isFalse();
        assertThat(result.authorizationGranted()).isFalse();
        assertThat(result.realSecurityProviderConfigured()).isFalse();
        assertThat(result.consumerAuthorizationAvailable()).isFalse();
        assertThat(result.consentVerified()).isFalse();
        assertThat(result.purposeApproved()).isFalse();
        assertThat(result.dataScopeApproved()).isFalse();
        assertThat(result.consentProviderConfigured()).isFalse();
        assertThat(result.consentAvailable()).isFalse();
        assertThat(result.scopeEvaluated()).isFalse();
        assertThat(result.minimizationEvaluated()).isFalse();
        assertThat(result.purposeScopeAlignmentEvaluated()).isFalse();
        assertThat(result.clinicalDataScopeProviderConfigured()).isFalse();
        assertThat(result.clinicalDataScopeApprovalAvailable()).isFalse();
        assertThat(result.accessRequestEvaluated()).isFalse();
        assertThat(result.clinicalDataAccessRequested()).isFalse();
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertThat(result.clinicalDataAccessAllowed()).isFalse();
        assertThat(result.clinicalDataAccessGrantAvailable()).isFalse();
        assertThat(result.clinicalDataAccessEnforced()).isFalse();
        assertThat(result.clinicalDataAccessProviderConfigured()).isFalse();
        assertThat(result.clinicalDataAccessAuthorizationAvailable()).isFalse();
        assertThat(result.enforcementDecisionAvailable()).isFalse();
        assertThat(result.enforcementDecisionEvaluated()).isFalse();
        assertThat(result.clinicalDataAccessEnforcementAvailable()).isFalse();
        assertThat(result.clinicalDataAccessEnforcementProviderConfigured()).isFalse();
        assertThat(result.clinicalDataAccessEnforcementExecuted()).isFalse();
        assertThat(result.executionDecisionAvailable()).isFalse();
        assertThat(result.executionDecisionEvaluated()).isFalse();
        assertThat(result.enforcementExecutionAvailable()).isFalse();
        assertThat(result.enforcementExecutionProviderConfigured()).isFalse();
        assertThat(result.enforcementExecutionPerformed()).isFalse();
        assertThat(result.verificationDecisionAvailable()).isFalse();
        assertThat(result.verificationDecisionEvaluated()).isFalse();
        assertThat(result.executionEvidenceAvailable()).isFalse();
        assertThat(result.executionEvidenceEvaluated()).isFalse();
        assertThat(result.executionVerificationAvailable()).isFalse();
        assertThat(result.executionVerificationProviderConfigured()).isFalse();
        assertThat(result.executionVerified()).isFalse();
        assertThat(result.realAuthorizationRequired()).isTrue();
    }

    private static AiConsumerClinicalDataEnforcementExecutionResult validExecution() {
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(completeEpic());
        DeterministicAgentResult agent =
                DeterministicAgent.evaluate(DeterministicAgentInput.of(completeEpic(), diagnosis));
        FirstAiResult firstAi = FirstAiComponent.process(
                AiBoundaryService.prepare(AiBoundaryInput.of(completeEpic(), diagnosis, agent), "corr-lab"));
        AiConsumerContract contract = AiConsumerContractService.prepare(AiExecutionGate.evaluate(firstAi));
        return AiConsumerClinicalDataEnforcementExecutionBoundary.evaluate(
                AiConsumerClinicalDataEnforcementBoundary.evaluate(
                        AiConsumerClinicalDataAccessBoundary.evaluate(
                                AiConsumerDataScopeBoundary.evaluate(
                                        AiConsumerConsentBoundary.evaluate(
                                                AiConsumerAuthorizationBoundary.evaluate(
                                                        AiHandoffAuthorizationBoundary.evaluate(
                                                                AiConsumerReadiness.evaluate(
                                                                        AiConsumerPolicy.evaluate(
                                                                                AiConsumerPolicyInput.of(
                                                                                        contract,
                                                                                        AiConsumerIdentity
                                                                                                .laboratory()))))))))));
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
