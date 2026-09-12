package lab.healthcare.fhir.aiconsumerauthorization;

import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
import lab.healthcare.fhir.aiconsumer.AiConsumerContract;
import lab.healthcare.fhir.aiconsumer.AiConsumerContractService;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerIdentity;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicy;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyInput;
import lab.healthcare.fhir.aiconsumerreadiness.AiConsumerReadiness;
import lab.healthcare.fhir.aihandoffauthorization.AiHandoffAuthorizationBoundary;
import lab.healthcare.fhir.aihandoffauthorization.AiHandoffAuthorizationResult;
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

class AiConsumerAuthorizationBoundaryTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T22:00:00Z");

    @Test
    void validHandoffWithoutRealSecurityStaysUnimplemented() {
        AiConsumerAuthorizationResult result = AiConsumerAuthorizationBoundary.evaluate(validHandoff());

        assertThat(result.status()).isEqualTo(AiConsumerAuthorizationStatus.AUTHORIZATION_NOT_IMPLEMENTED);
        assertThat(result.reason())
                .isEqualTo(AiConsumerAuthorizationReasonCodes.REAL_AUTHENTICATION_AUTHORIZATION_NOT_IMPLEMENTED);
        assertThat(result.authenticationDisplay()).isEqualTo(AiConsumerAuthorizationResult.NOT_AUTHENTICATED);
        assertSafeInvariants(result);
    }

    @Test
    void missingHandoffResultIsBlocked() {
        AiConsumerAuthorizationResult result =
                AiConsumerAuthorizationBoundary.evaluate((AiHandoffAuthorizationResult) null);

        assertThat(result.status()).isEqualTo(AiConsumerAuthorizationStatus.BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerAuthorizationReasonCodes.MISSING_HANDOFF_AUTHORIZATION_RESULT);
        assertSafeInvariants(result);
    }

    @Test
    void unexpectedHandoffAuthorizationIsBlockedAndNotPropagated() {
        AiConsumerAuthorizationResult result = AiConsumerAuthorizationBoundary.evaluate(
                AiConsumerAuthorizationInput.from(validHandoff()).withHandoffAuthorized(true));

        assertThat(result.status()).isEqualTo(AiConsumerAuthorizationStatus.BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerAuthorizationReasonCodes.UNEXPECTED_HANDOFF_AUTHORIZATION);
        assertThat(result.handoffAuthorized()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void declaredIdentityWithoutVerificationIsNotAuthenticated() {
        AiConsumerAuthorizationResult result = AiConsumerAuthorizationBoundary.evaluate(
                validHandoff(), ConsumerSecurityContext.laboratory().withConsumerIdentifierPresent(true));

        assertThat(result.status()).isEqualTo(AiConsumerAuthorizationStatus.NOT_AUTHENTICATED);
        assertThat(result.reason()).isEqualTo(AiConsumerAuthorizationReasonCodes.CONSUMER_IDENTITY_NOT_VERIFIED);
        assertSafeInvariants(result);
    }

    @Test
    void untrustedAuthenticationAssertionIsBlocked() {
        AiConsumerAuthorizationResult result = AiConsumerAuthorizationBoundary.evaluate(
                validHandoff(), ConsumerSecurityContext.laboratory().withAuthenticationVerified(true));

        assertThat(result.status()).isEqualTo(AiConsumerAuthorizationStatus.BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerAuthorizationReasonCodes.UNTRUSTED_AUTHENTICATION_ASSERTION);
        assertThat(result.authenticationVerified()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void untrustedAuthorizationAssertionIsBlocked() {
        AiConsumerAuthorizationResult result = AiConsumerAuthorizationBoundary.evaluate(
                validHandoff(), ConsumerSecurityContext.laboratory().withAuthorizationGranted(true));

        assertThat(result.status()).isEqualTo(AiConsumerAuthorizationStatus.BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerAuthorizationReasonCodes.UNTRUSTED_AUTHORIZATION_ASSERTION);
        assertThat(result.authorizationGranted()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void conceptualScopeWithoutVerificationIsNotAuthorized() {
        AiConsumerAuthorizationResult result = AiConsumerAuthorizationBoundary.evaluate(
                validHandoff(),
                ConsumerSecurityContext.laboratory().withRequestedScope(AiConsumerAuthorizationScopes.HANDOFF_REQUEST));

        assertThat(result.status()).isEqualTo(AiConsumerAuthorizationStatus.NOT_AUTHORIZED);
        assertThat(result.reason()).isEqualTo(AiConsumerAuthorizationReasonCodes.SCOPE_NOT_VERIFIED);
        assertSafeInvariants(result);
    }

    @Test
    void missingTenantContextIsBlocked() {
        AiConsumerAuthorizationResult result = AiConsumerAuthorizationBoundary.evaluate(
                validHandoff(), ConsumerSecurityContext.laboratory().withTenantContextPresent(false));

        assertThat(result.status()).isEqualTo(AiConsumerAuthorizationStatus.BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerAuthorizationReasonCodes.MISSING_TENANT_CONTEXT);
        assertSafeInvariants(result);
    }

    @Test
    void contextAbsentFallsBackToHandoffNotAuthorized() {
        AiConsumerAuthorizationResult result = AiConsumerAuthorizationBoundary.evaluate(
                validHandoff(), ConsumerSecurityContext.laboratory().withContextPresent(false));

        assertThat(result.status()).isEqualTo(AiConsumerAuthorizationStatus.AUTHORIZATION_NOT_IMPLEMENTED);
        assertThat(result.reason()).isEqualTo(AiConsumerAuthorizationReasonCodes.HANDOFF_NOT_AUTHORIZED);
        assertSafeInvariants(result);
    }

    private static void assertSafeInvariants(AiConsumerAuthorizationResult result) {
        assertThat(result.handoffAuthorized()).isFalse();
        assertThat(result.dispatchPerformed()).isFalse();
        assertThat(result.externalAuthorizationAvailable()).isFalse();
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.processingStatus()).isEqualTo(AiConsumerAuthorizationResult.NOT_EXECUTED);
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerAuthorizationResult.NOT_DISPATCHED);
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.authenticationVerified()).isFalse();
        assertThat(result.authorizationGranted()).isFalse();
        assertThat(result.realSecurityProviderConfigured()).isFalse();
        assertThat(result.consumerAuthorizationAvailable()).isFalse();
    }

    private static AiHandoffAuthorizationResult validHandoff() {
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(completeEpic());
        DeterministicAgentResult agent =
                DeterministicAgent.evaluate(DeterministicAgentInput.of(completeEpic(), diagnosis));
        FirstAiResult firstAi = FirstAiComponent.process(
                AiBoundaryService.prepare(AiBoundaryInput.of(completeEpic(), diagnosis, agent), "corr-lab"));
        AiConsumerContract contract = AiConsumerContractService.prepare(AiExecutionGate.evaluate(firstAi));
        return AiHandoffAuthorizationBoundary.evaluate(
                AiConsumerReadiness.evaluate(AiConsumerPolicy.evaluate(
                        AiConsumerPolicyInput.of(contract, AiConsumerIdentity.laboratory()))));
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
