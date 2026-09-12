package lab.healthcare.fhir.aiconsumerenforcementexecution;

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
import lab.healthcare.fhir.aiconsumerenforcement.AiConsumerClinicalDataEnforcementResult;
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

class AiConsumerClinicalDataEnforcementExecutionBoundaryTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T23:30:00Z");

    @Test
    void validEnforcementWithoutExecutionProviderIsNotExecuted() {
        AiConsumerClinicalDataEnforcementExecutionResult result =
                AiConsumerClinicalDataEnforcementExecutionBoundary.evaluate(validEnforcement());

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionStatus.NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS);
        assertThat(result.reason())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionReasonCodes.ENFORCEMENT_NOT_EXECUTED);
        assertThat(result.executionDecisionAvailable()).isFalse();
        assertThat(result.executionDecisionEvaluated()).isFalse();
        assertThat(result.enforcementExecutionAvailable()).isFalse();
        assertThat(result.enforcementExecutionPerformed()).isFalse();
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertThat(result.clinicalDataAccessAllowed()).isFalse();
        assertThat(result.clinicalDataAccessEnforced()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void missingEnforcementResultIsNotAvailable() {
        AiConsumerClinicalDataEnforcementExecutionResult result =
                AiConsumerClinicalDataEnforcementExecutionBoundary.evaluate(
                        (AiConsumerClinicalDataEnforcementResult) null);

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionStatus.EXECUTION_INPUT_NOT_AVAILABLE);
        assertThat(result.reason())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionReasonCodes.MISSING_ENFORCEMENT_RESULT);
        assertSafeInvariants(result);
    }

    @Test
    void unavailableEnforcementDecisionRequiresDecision() {
        AiConsumerClinicalDataEnforcementExecutionResult result =
                AiConsumerClinicalDataEnforcementExecutionBoundary.evaluate(
                        validEnforcement(),
                        ClinicalDataEnforcementExecutionContext.laboratory()
                                .withEnforcementDecisionCheckAttempted(true));

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionStatus.EXECUTION_REQUIRES_ENFORCEMENT_DECISION);
        assertThat(result.enforcementExecutionPerformed()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void missingRealAuthorizationRequiresProvider() {
        AiConsumerClinicalDataEnforcementExecutionResult result =
                AiConsumerClinicalDataEnforcementExecutionBoundary.evaluate(
                        validEnforcement(),
                        ClinicalDataEnforcementExecutionContext.laboratory()
                                .withAuthorizationEvaluationAttempted(true));

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionStatus.EXECUTION_REQUIRES_REAL_AUTHORIZATION);
        assertThat(result.realAuthorizationRequired()).isTrue();
        assertSafeInvariants(result);
    }

    @Test
    void humanReviewCheckStaysRequired() {
        AiConsumerClinicalDataEnforcementExecutionResult result =
                AiConsumerClinicalDataEnforcementExecutionBoundary.evaluate(
                        validEnforcement(),
                        ClinicalDataEnforcementExecutionContext.laboratory().withHumanReviewCheckAttempted(true));

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionStatus.EXECUTION_REQUIRES_HUMAN_REVIEW);
        assertThat(result.requiresHumanReview()).isTrue();
        assertSafeInvariants(result);
    }

    @Test
    void manipulatedContextCannotExecuteEnforcement() {
        AiConsumerClinicalDataEnforcementExecutionResult result =
                AiConsumerClinicalDataEnforcementExecutionBoundary.evaluate(
                        validEnforcement(),
                        ClinicalDataEnforcementExecutionContext.laboratory().withPositiveClaims());

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionStatus.EXECUTION_BLOCKED);
        assertThat(result.reason())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionReasonCodes.UNTRUSTED_EXECUTION_ASSERTION);
        assertThat(result.enforcementExecutionAvailable()).isFalse();
        assertThat(result.enforcementExecutionPerformed()).isFalse();
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void grantedInputFlagCannotManufacturePermission() {
        AiConsumerClinicalDataEnforcementExecutionResult result =
                AiConsumerClinicalDataEnforcementExecutionBoundary.evaluate(
                        AiConsumerClinicalDataEnforcementExecutionInput.from(validEnforcement())
                                .withClinicalDataAccessGranted(true));

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionStatus.EXECUTION_BLOCKED);
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void missingTenantScopeIsBlocked() {
        AiConsumerClinicalDataEnforcementExecutionResult result =
                AiConsumerClinicalDataEnforcementExecutionBoundary.evaluate(
                        validEnforcement(),
                        ClinicalDataEnforcementExecutionContext.laboratory().withTenantScopePresent(false));

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionStatus.EXECUTION_BLOCKED);
        assertThat(result.reason())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionReasonCodes.MISSING_TENANT_SCOPE);
        assertSafeInvariants(result);
    }

    @Test
    void factoryRejectsEffectiveExecutionFlags() {
        assertThatThrownBy(() -> unsafeResult(true, false, false))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("must not grant clinical access");
        assertThatThrownBy(() -> unsafeResult(false, true, false))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("must not allow clinical data access");
        assertThatThrownBy(() -> unsafeResult(false, false, true))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("must not enforce access");
    }

    @Test
    void evaluationIsDeterministicAndHasNoClinicalPayload() {
        AiConsumerClinicalDataEnforcementExecutionResult first =
                AiConsumerClinicalDataEnforcementExecutionBoundary.evaluate(validEnforcement());
        AiConsumerClinicalDataEnforcementExecutionResult second =
                AiConsumerClinicalDataEnforcementExecutionBoundary.evaluate(validEnforcement());

        assertThat(first).isEqualTo(second);
        assertThat(first.toString()).doesNotContain("access_token");
        assertThat(first.toString()).doesNotContain("Patient/");
        assertThat(first.toString()).doesNotContain("\"resourceType\"");
        assertSafeInvariants(first);
    }

    private static AiConsumerClinicalDataEnforcementExecutionResult unsafeResult(
            boolean granted, boolean allowed, boolean enforced) {
        return new AiConsumerClinicalDataEnforcementExecutionResult(
                AiConsumerClinicalDataEnforcementExecutionResult.VERSION_V1,
                AiConsumerClinicalDataEnforcementExecutionStatus.NOT_EXECUTED_FOR_CLINICAL_DATA_ACCESS,
                AiConsumerClinicalDataEnforcementExecutionReasonCodes.ENFORCEMENT_NOT_EXECUTED,
                AiConsumerClinicalDataEnforcementExecutionOperations.EVALUATE_CLINICAL_DATA_ENFORCEMENT_EXECUTION,
                true,
                ClinicalDataEnforcementExecutionContext.SOURCE_LABORATORY,
                AiConsumerClinicalDataEnforcementExecutionResult.EVALUATION_NOT_EVALUATED,
                AiConsumerClinicalDataEnforcementExecutionReasonCodes.ENFORCEMENT_NOT_EXECUTED,
                false,
                false,
                false,
                false,
                false,
                true,
                granted,
                allowed,
                enforced,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                false,
                AiConsumerClinicalDataEnforcementExecutionResult.NOT_EXECUTED,
                AiConsumerClinicalDataEnforcementExecutionResult.NOT_DISPATCHED,
                true);
    }

    private static void assertSafeInvariants(AiConsumerClinicalDataEnforcementExecutionResult result) {
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.processingStatus())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionResult.NOT_EXECUTED);
        assertThat(result.dispatchStatus())
                .isEqualTo(AiConsumerClinicalDataEnforcementExecutionResult.NOT_DISPATCHED);
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
        assertThat(result.realAuthorizationRequired()).isTrue();
    }

    private static AiConsumerClinicalDataEnforcementResult validEnforcement() {
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(completeEpic());
        DeterministicAgentResult agent =
                DeterministicAgent.evaluate(DeterministicAgentInput.of(completeEpic(), diagnosis));
        FirstAiResult firstAi = FirstAiComponent.process(
                AiBoundaryService.prepare(AiBoundaryInput.of(completeEpic(), diagnosis, agent), "corr-lab"));
        AiConsumerContract contract = AiConsumerContractService.prepare(AiExecutionGate.evaluate(firstAi));
        return AiConsumerClinicalDataEnforcementBoundary.evaluate(
                AiConsumerClinicalDataAccessBoundary.evaluate(
                        AiConsumerDataScopeBoundary.evaluate(
                                AiConsumerConsentBoundary.evaluate(
                                        AiConsumerAuthorizationBoundary.evaluate(
                                                AiHandoffAuthorizationBoundary.evaluate(
                                                        AiConsumerReadiness.evaluate(AiConsumerPolicy.evaluate(
                                                                AiConsumerPolicyInput.of(
                                                                        contract,
                                                                        AiConsumerIdentity.laboratory())))))))));
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
