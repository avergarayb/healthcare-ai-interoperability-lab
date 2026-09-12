package lab.healthcare.fhir.aiconsumerenforcement;

import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
import lab.healthcare.fhir.aiconsumer.AiConsumerContract;
import lab.healthcare.fhir.aiconsumer.AiConsumerContractService;
import lab.healthcare.fhir.aiconsumeraccess.AiConsumerClinicalDataAccessBoundary;
import lab.healthcare.fhir.aiconsumeraccess.AiConsumerClinicalDataAccessResult;
import lab.healthcare.fhir.aiconsumeraccess.ClinicalDataAccessRequestContext;
import lab.healthcare.fhir.aiconsumerauthorization.AiConsumerAuthorizationBoundary;
import lab.healthcare.fhir.aiconsumerconsent.AiConsumerConsentBoundary;
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

class AiConsumerClinicalDataEnforcementBoundaryTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T23:30:00Z");

    @Test
    void validAccessWithoutEnforcementProviderIsNotEnforced() {
        AiConsumerClinicalDataEnforcementResult result =
                AiConsumerClinicalDataEnforcementBoundary.evaluate(validAccess());

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementStatus.NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS);
        assertThat(result.reason()).isEqualTo(AiConsumerClinicalDataEnforcementReasonCodes.ACCESS_NOT_GRANTED);
        assertThat(result.enforcementDecisionAvailable()).isFalse();
        assertThat(result.enforcementDecisionEvaluated()).isFalse();
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertThat(result.clinicalDataAccessAllowed()).isFalse();
        assertThat(result.clinicalDataAccessEnforced()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void missingAccessResultIsNotAvailable() {
        AiConsumerClinicalDataEnforcementResult result =
                AiConsumerClinicalDataEnforcementBoundary.evaluate((AiConsumerClinicalDataAccessResult) null);

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementStatus.ENFORCEMENT_INPUT_NOT_AVAILABLE);
        assertThat(result.reason()).isEqualTo(AiConsumerClinicalDataEnforcementReasonCodes.MISSING_ACCESS_RESULT);
        assertSafeInvariants(result);
    }

    @Test
    void priorAccessNotGrantedBlocksEnforcement() {
        AiConsumerClinicalDataEnforcementResult result =
                AiConsumerClinicalDataEnforcementBoundary.evaluate(validAccess());

        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertThat(result.clinicalDataAccessAllowed()).isFalse();
        assertThat(result.clinicalDataAccessEnforced()).isFalse();
        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementStatus.NOT_ENFORCED_FOR_CLINICAL_DATA_ACCESS);
        assertSafeInvariants(result);
    }

    @Test
    void pendingAccessRequestRequiresAccessDecision() {
        AiConsumerClinicalDataEnforcementResult result = AiConsumerClinicalDataEnforcementBoundary.evaluate(
                pendingAccessRequest(),
                ClinicalDataEnforcementContext.laboratory());

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementStatus.ENFORCEMENT_REQUIRES_ACCESS_DECISION);
        assertThat(result.enforcementDecisionAvailable()).isFalse();
        assertThat(result.clinicalDataAccessEnforced()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void missingRealAuthorizationRequiresProvider() {
        AiConsumerClinicalDataEnforcementResult result = AiConsumerClinicalDataEnforcementBoundary.evaluate(
                validAccess(),
                ClinicalDataEnforcementContext.laboratory().withAuthorizationEvaluationAttempted(true));

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataEnforcementStatus.ENFORCEMENT_REQUIRES_REAL_AUTHORIZATION);
        assertThat(result.realAuthorizationRequired()).isTrue();
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertThat(result.clinicalDataAccessAllowed()).isFalse();
        assertThat(result.clinicalDataAccessEnforced()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void manipulatedContextCannotEnforceAccess() {
        AiConsumerClinicalDataEnforcementResult result = AiConsumerClinicalDataEnforcementBoundary.evaluate(
                validAccess(), ClinicalDataEnforcementContext.laboratory().withPositiveClaims());

        assertThat(result.status()).isEqualTo(AiConsumerClinicalDataEnforcementStatus.ENFORCEMENT_BLOCKED);
        assertThat(result.reason())
                .isEqualTo(AiConsumerClinicalDataEnforcementReasonCodes.UNTRUSTED_ENFORCEMENT_ASSERTION);
        assertThat(result.enforcementDecisionAvailable()).isFalse();
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertThat(result.clinicalDataAccessAllowed()).isFalse();
        assertThat(result.clinicalDataAccessEnforced()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void missingTenantScopeIsBlocked() {
        AiConsumerClinicalDataEnforcementResult result = AiConsumerClinicalDataEnforcementBoundary.evaluate(
                validAccess(), ClinicalDataEnforcementContext.laboratory().withTenantScopePresent(false));

        assertThat(result.status()).isEqualTo(AiConsumerClinicalDataEnforcementStatus.ENFORCEMENT_BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerClinicalDataEnforcementReasonCodes.MISSING_TENANT_SCOPE);
        assertSafeInvariants(result);
    }

    @Test
    void evaluationIsDeterministicAndHasNoClinicalPayload() {
        AiConsumerClinicalDataEnforcementResult first =
                AiConsumerClinicalDataEnforcementBoundary.evaluate(validAccess());
        AiConsumerClinicalDataEnforcementResult second =
                AiConsumerClinicalDataEnforcementBoundary.evaluate(validAccess());

        assertThat(first).isEqualTo(second);
        assertThat(first.toString()).doesNotContain("access_token");
        assertThat(first.toString()).doesNotContain("Patient/");
        assertThat(first.toString()).doesNotContain("\"resourceType\"");
        assertSafeInvariants(first);
    }

    private static void assertSafeInvariants(AiConsumerClinicalDataEnforcementResult result) {
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.processingStatus()).isEqualTo(AiConsumerClinicalDataEnforcementResult.NOT_EXECUTED);
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerClinicalDataEnforcementResult.NOT_DISPATCHED);
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
        assertThat(result.realAuthorizationRequired()).isTrue();
    }

    private static AiConsumerClinicalDataAccessResult validAccess() {
        return AiConsumerClinicalDataAccessBoundary.evaluate(validScope());
    }

    private static AiConsumerClinicalDataAccessResult pendingAccessRequest() {
        return AiConsumerClinicalDataAccessBoundary.evaluate(
                validScope(),
                ClinicalDataAccessRequestContext.laboratory()
                        .withRequestDeclared(true)
                        .withScopeReferencePresent(true));
    }

    private static lab.healthcare.fhir.aiconsumerscope.AiConsumerDataScopeResult validScope() {
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(completeEpic());
        DeterministicAgentResult agent =
                DeterministicAgent.evaluate(DeterministicAgentInput.of(completeEpic(), diagnosis));
        FirstAiResult firstAi = FirstAiComponent.process(
                AiBoundaryService.prepare(AiBoundaryInput.of(completeEpic(), diagnosis, agent), "corr-lab"));
        AiConsumerContract contract = AiConsumerContractService.prepare(AiExecutionGate.evaluate(firstAi));
        return AiConsumerDataScopeBoundary.evaluate(
                AiConsumerConsentBoundary.evaluate(
                        AiConsumerAuthorizationBoundary.evaluate(
                                AiHandoffAuthorizationBoundary.evaluate(
                                        AiConsumerReadiness.evaluate(AiConsumerPolicy.evaluate(
                                                AiConsumerPolicyInput.of(
                                                        contract, AiConsumerIdentity.laboratory())))))));
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
