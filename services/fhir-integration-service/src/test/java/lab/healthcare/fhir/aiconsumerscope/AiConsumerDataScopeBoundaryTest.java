package lab.healthcare.fhir.aiconsumerscope;

import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
import lab.healthcare.fhir.aiconsumer.AiConsumerContract;
import lab.healthcare.fhir.aiconsumer.AiConsumerContractService;
import lab.healthcare.fhir.aiconsumerauthorization.AiConsumerAuthorizationBoundary;
import lab.healthcare.fhir.aiconsumerconsent.AiConsumerConsentBoundary;
import lab.healthcare.fhir.aiconsumerconsent.AiConsumerConsentResult;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerIdentity;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicy;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyInput;
import lab.healthcare.fhir.aiconsumerreadiness.AiConsumerReadiness;
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

class AiConsumerDataScopeBoundaryTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T23:30:00Z");

    @Test
    void validConsentWithoutScopeProviderIsNotReady() {
        AiConsumerDataScopeResult result = AiConsumerDataScopeBoundary.evaluate(validConsent());

        assertThat(result.status()).isEqualTo(AiConsumerDataScopeStatus.NOT_READY_FOR_CLINICAL_DATA_ACCESS);
        assertThat(result.reason()).isEqualTo(AiConsumerDataScopeReasonCodes.CONSENT_NOT_AVAILABLE);
        assertThat(result.scopeDeclared()).isFalse();
        assertThat(result.scopeEvaluated()).isFalse();
        assertThat(result.minimizationEvaluated()).isFalse();
        assertThat(result.purposeScopeAlignmentEvaluated()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void missingConsentResultIsBlocked() {
        AiConsumerDataScopeResult result =
                AiConsumerDataScopeBoundary.evaluate((AiConsumerConsentResult) null);

        assertThat(result.status()).isEqualTo(AiConsumerDataScopeStatus.SCOPE_BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerDataScopeReasonCodes.MISSING_CONSENT_RESULT);
        assertSafeInvariants(result);
    }

    @Test
    void unavailableConsentBlocksScopeApproval() {
        AiConsumerDataScopeResult result = AiConsumerDataScopeBoundary.evaluate(validConsent());

        assertThat(result.consentAvailable()).isFalse();
        assertThat(result.consentVerified()).isFalse();
        assertThat(result.status()).isEqualTo(AiConsumerDataScopeStatus.NOT_READY_FOR_CLINICAL_DATA_ACCESS);
        assertSafeInvariants(result);
    }

    @Test
    void unverifiedPurposeBlocksPositiveMinimization() {
        AiConsumerDataScopeResult result = AiConsumerDataScopeBoundary.evaluate(validConsent());

        assertThat(result.purposeApproved()).isFalse();
        assertThat(result.minimizationEvaluated()).isFalse();
        assertThat(result.purposeScopeAlignmentEvaluated()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void explicitEmptyScopeIsNotDeclared() {
        AiConsumerDataScopeResult result = AiConsumerDataScopeBoundary.evaluate(
                validConsent(), ConsumerDataScopeContext.laboratory().withDeclarationAttempted(true));

        assertThat(result.status()).isEqualTo(AiConsumerDataScopeStatus.DATA_SCOPE_NOT_DECLARED);
        assertThat(result.reason()).isEqualTo(AiConsumerDataScopeReasonCodes.DATA_SCOPE_NOT_DECLARED);
        assertThat(result.scopeDeclared()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void syntheticDeclaredScopeIsNotEvaluated() {
        AiConsumerDataScopeResult result = AiConsumerDataScopeBoundary.evaluate(
                validConsent(),
                ConsumerDataScopeContext.laboratory()
                        .withDeclaredDataCategories(List.of(ConsumerDataScopeCategories.CONDITION_SUMMARY)));

        assertThat(result.status()).isEqualTo(AiConsumerDataScopeStatus.DATA_SCOPE_DECLARED_NOT_EVALUATED);
        assertThat(result.scopeDeclared()).isTrue();
        assertThat(result.scopeEvaluated()).isFalse();
        assertThat(result.minimizationEvaluated()).isFalse();
        assertThat(result.declaredDataCategories()).containsExactly("CONDITION_SUMMARY");
        assertSafeInvariants(result);
    }

    @Test
    void minimizationStaysNotEvaluated() {
        AiConsumerDataScopeResult first = AiConsumerDataScopeBoundary.evaluate(validConsent());
        AiConsumerDataScopeResult second = AiConsumerDataScopeBoundary.evaluate(validConsent());

        assertThat(first.minimizationEvaluated()).isFalse();
        assertThat(first.minimizationStatus()).isEqualTo(AiConsumerDataScopeResult.MINIMIZATION_NOT_EVALUATED);
        assertThat(first.status()).isEqualTo(second.status());
        assertThat(first.reason()).isEqualTo(second.reason());
        assertSafeInvariants(first);
    }

    @Test
    void purposeScopeAlignmentStaysNotEvaluated() {
        AiConsumerDataScopeResult result = AiConsumerDataScopeBoundary.evaluate(validConsent());

        assertThat(result.purposeScopeAlignmentEvaluated()).isFalse();
        assertThat(result.purposeScopeAlignmentStatus()).isEqualTo(PurposeScopeAlignmentStatus.NOT_DECLARED);
        assertSafeInvariants(result);
    }

    @Test
    void missingTenantScopeIsBlocked() {
        AiConsumerDataScopeResult result = AiConsumerDataScopeBoundary.evaluate(
                validConsent(), ConsumerDataScopeContext.laboratory().withTenantScopePresent(false));

        assertThat(result.status()).isEqualTo(AiConsumerDataScopeStatus.SCOPE_BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerDataScopeReasonCodes.MISSING_TENANT_SCOPE);
        assertSafeInvariants(result);
    }

    @Test
    void syntheticTenantIsUntrustedMetadata() {
        AiConsumerDataScopeResult result = AiConsumerDataScopeBoundary.evaluate(validConsent());

        assertThat(result.declaredTenantScope()).isEqualTo("LAB");
        assertThat(result.clinicalDataAccessAllowed()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void manipulatedContextCannotAllowClinicalAccess() {
        AiConsumerDataScopeResult result = AiConsumerDataScopeBoundary.evaluate(
                validConsent(),
                ConsumerDataScopeContext.laboratory()
                        .withClinicalDataAccessAllowedClaim(true)
                        .withScopeEvaluatedClaim(true));

        assertThat(result.status()).isEqualTo(AiConsumerDataScopeStatus.SCOPE_BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerDataScopeReasonCodes.UNTRUSTED_SCOPE_ASSERTION);
        assertThat(result.clinicalDataAccessAllowed()).isFalse();
        assertThat(result.scopeEvaluated()).isFalse();
        assertSafeInvariants(result);
    }

    private static void assertSafeInvariants(AiConsumerDataScopeResult result) {
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.processingStatus()).isEqualTo(AiConsumerDataScopeResult.NOT_EXECUTED);
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerDataScopeResult.NOT_DISPATCHED);
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
        assertThat(result.clinicalDataAccessAllowed()).isFalse();
        assertThat(result.scopeEvaluated()).isFalse();
        assertThat(result.minimizationEvaluated()).isFalse();
        assertThat(result.purposeScopeAlignmentEvaluated()).isFalse();
        assertThat(result.clinicalDataScopeProviderConfigured()).isFalse();
        assertThat(result.clinicalDataScopeApprovalAvailable()).isFalse();
        assertThat(result.clinicalDataAccessRequested()).isFalse();
        assertThat(result.clinicalDataAccessGranted()).isFalse();
    }

    private static AiConsumerConsentResult validConsent() {
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(completeEpic());
        DeterministicAgentResult agent =
                DeterministicAgent.evaluate(DeterministicAgentInput.of(completeEpic(), diagnosis));
        FirstAiResult firstAi = FirstAiComponent.process(
                AiBoundaryService.prepare(AiBoundaryInput.of(completeEpic(), diagnosis, agent), "corr-lab"));
        AiConsumerContract contract = AiConsumerContractService.prepare(AiExecutionGate.evaluate(firstAi));
        return AiConsumerConsentBoundary.evaluate(
                AiConsumerAuthorizationBoundary.evaluate(
                        AiHandoffAuthorizationBoundary.evaluate(
                                AiConsumerReadiness.evaluate(AiConsumerPolicy.evaluate(
                                        AiConsumerPolicyInput.of(contract, AiConsumerIdentity.laboratory()))))));
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
