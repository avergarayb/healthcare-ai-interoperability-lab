package lab.healthcare.fhir.aiconsumerconsent;

import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
import lab.healthcare.fhir.aiconsumer.AiConsumerContract;
import lab.healthcare.fhir.aiconsumer.AiConsumerContractService;
import lab.healthcare.fhir.aiconsumerauthorization.AiConsumerAuthorizationBoundary;
import lab.healthcare.fhir.aiconsumerauthorization.AiConsumerAuthorizationResult;
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

class AiConsumerConsentBoundaryTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T23:00:00Z");

    @Test
    void validAuthorizationWithoutConsentProviderStaysUnimplemented() {
        AiConsumerConsentResult result = AiConsumerConsentBoundary.evaluate(validAuthorization());

        assertThat(result.status()).isEqualTo(AiConsumerConsentStatus.CONSENT_NOT_IMPLEMENTED);
        assertThat(result.reason()).isEqualTo(AiConsumerConsentReasonCodes.CONSUMER_AUTHORIZATION_NOT_AVAILABLE);
        assertThat(result.purposeDisplay()).isEqualTo(AiConsumerConsentResult.PURPOSE_NOT_VERIFIED);
        assertThat(result.dataScopeDisplay()).isEqualTo(AiConsumerConsentResult.DATA_SCOPE_NOT_VERIFIED);
        assertSafeInvariants(result);
    }

    @Test
    void missingAuthorizationResultIsBlocked() {
        AiConsumerConsentResult result =
                AiConsumerConsentBoundary.evaluate((AiConsumerAuthorizationResult) null);

        assertThat(result.status()).isEqualTo(AiConsumerConsentStatus.BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerConsentReasonCodes.MISSING_CONSUMER_AUTHORIZATION_RESULT);
        assertSafeInvariants(result);
    }

    @Test
    void unavailableConsumerAuthorizationStaysUnimplemented() {
        AiConsumerConsentResult result = AiConsumerConsentBoundary.evaluate(validAuthorization());

        assertThat(result.status()).isEqualTo(AiConsumerConsentStatus.CONSENT_NOT_IMPLEMENTED);
        assertThat(result.reason()).isEqualTo(AiConsumerConsentReasonCodes.CONSUMER_AUTHORIZATION_NOT_AVAILABLE);
        assertThat(result.consumerAuthorizationAvailable()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void unexpectedConsumerAuthorizationIsBlockedAndNotPropagated() {
        AiConsumerConsentResult result = AiConsumerConsentBoundary.evaluate(
                AiConsumerConsentInput.from(validAuthorization()).withConsumerAuthorizationAvailable(true));

        assertThat(result.status()).isEqualTo(AiConsumerConsentStatus.BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerConsentReasonCodes.UNEXPECTED_CONSUMER_AUTHORIZATION);
        assertThat(result.consumerAuthorizationAvailable()).isFalse();
        assertThat(result.authorizationGranted()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void missingConsentContextIsNotImplemented() {
        AiConsumerConsentResult result = AiConsumerConsentBoundary.evaluate(
                validAuthorization(), ConsumerConsentContext.laboratory().withContextPresent(false));

        assertThat(result.status()).isEqualTo(AiConsumerConsentStatus.CONSENT_NOT_IMPLEMENTED);
        assertThat(result.reason()).isEqualTo(AiConsumerConsentReasonCodes.MISSING_CONSENT_CONTEXT);
        assertSafeInvariants(result);
    }

    @Test
    void untrustedConsentAssertionIsBlocked() {
        AiConsumerConsentResult result = AiConsumerConsentBoundary.evaluate(
                validAuthorization(), ConsumerConsentContext.laboratory().withConsentVerified(true));

        assertThat(result.status()).isEqualTo(AiConsumerConsentStatus.BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerConsentReasonCodes.UNTRUSTED_CONSENT_ASSERTION);
        assertThat(result.consentVerified()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void unverifiedConsentReferenceIsNotImplemented() {
        AiConsumerConsentResult result = AiConsumerConsentBoundary.evaluate(
                validAuthorization(), ConsumerConsentContext.laboratory().withConsentReferencePresent(true));

        assertThat(result.status()).isEqualTo(AiConsumerConsentStatus.CONSENT_NOT_IMPLEMENTED);
        assertThat(result.reason()).isEqualTo(AiConsumerConsentReasonCodes.CONSENT_REFERENCE_NOT_VERIFIED);
        assertSafeInvariants(result);
    }

    @Test
    void missingPurposeIsNotVerified() {
        AiConsumerConsentResult result = AiConsumerConsentBoundary.evaluate(
                validAuthorization(),
                ConsumerConsentContext.laboratory()
                        .withPurposeDeclared(false)
                        .withRequestedPurpose(ConsumerConsentPurpose.UNKNOWN));

        assertThat(result.status()).isEqualTo(AiConsumerConsentStatus.PURPOSE_NOT_VERIFIED);
        assertThat(result.reason()).isEqualTo(AiConsumerConsentReasonCodes.MISSING_PURPOSE);
        assertSafeInvariants(result);
    }

    @Test
    void untrustedPurposeAssertionIsBlocked() {
        AiConsumerConsentResult result = AiConsumerConsentBoundary.evaluate(
                validAuthorization(), ConsumerConsentContext.laboratory().withPurposeApproved(true));

        assertThat(result.status()).isEqualTo(AiConsumerConsentStatus.BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerConsentReasonCodes.UNTRUSTED_PURPOSE_ASSERTION);
        assertThat(result.purposeApproved()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void missingDataScopeIsNotVerified() {
        AiConsumerConsentResult result = AiConsumerConsentBoundary.evaluate(
                validAuthorization(), ConsumerConsentContext.laboratory().withRequestedDataScope(""));

        assertThat(result.status()).isEqualTo(AiConsumerConsentStatus.DATA_SCOPE_NOT_VERIFIED);
        assertThat(result.reason()).isEqualTo(AiConsumerConsentReasonCodes.MISSING_DATA_SCOPE);
        assertSafeInvariants(result);
    }

    @Test
    void untrustedDataScopeAssertionIsBlocked() {
        AiConsumerConsentResult result = AiConsumerConsentBoundary.evaluate(
                validAuthorization(), ConsumerConsentContext.laboratory().withDataScopeApproved(true));

        assertThat(result.status()).isEqualTo(AiConsumerConsentStatus.BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerConsentReasonCodes.UNTRUSTED_DATA_SCOPE_ASSERTION);
        assertThat(result.dataScopeApproved()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void missingTenantContextIsBlocked() {
        AiConsumerConsentResult result = AiConsumerConsentBoundary.evaluate(
                validAuthorization(), ConsumerConsentContext.laboratory().withTenantContextPresent(false));

        assertThat(result.status()).isEqualTo(AiConsumerConsentStatus.BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerConsentReasonCodes.MISSING_TENANT_CONTEXT);
        assertSafeInvariants(result);
    }

    @Test
    void pendingHumanReviewStaysRequired() {
        AiConsumerConsentResult result = AiConsumerConsentBoundary.evaluate(
                validAuthorization(), ConsumerConsentContext.laboratory().withHumanReviewCompleted(false));

        assertThat(result.status()).isEqualTo(AiConsumerConsentStatus.HUMAN_REVIEW_REQUIRED);
        assertThat(result.reason()).isEqualTo(AiConsumerConsentReasonCodes.HUMAN_REVIEW_NOT_COMPLETED);
        assertThat(result.requiresHumanReview()).isTrue();
        assertSafeInvariants(result);
    }

    private static void assertSafeInvariants(AiConsumerConsentResult result) {
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.processingStatus()).isEqualTo(AiConsumerConsentResult.NOT_EXECUTED);
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerConsentResult.NOT_DISPATCHED);
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
        assertThat(result.humanReviewCompleted()).isFalse();
    }

    private static AiConsumerAuthorizationResult validAuthorization() {
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(completeEpic());
        DeterministicAgentResult agent =
                DeterministicAgent.evaluate(DeterministicAgentInput.of(completeEpic(), diagnosis));
        FirstAiResult firstAi = FirstAiComponent.process(
                AiBoundaryService.prepare(AiBoundaryInput.of(completeEpic(), diagnosis, agent), "corr-lab"));
        AiConsumerContract contract = AiConsumerContractService.prepare(AiExecutionGate.evaluate(firstAi));
        return AiConsumerAuthorizationBoundary.evaluate(
                AiHandoffAuthorizationBoundary.evaluate(
                        AiConsumerReadiness.evaluate(AiConsumerPolicy.evaluate(
                                AiConsumerPolicyInput.of(contract, AiConsumerIdentity.laboratory())))));
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
