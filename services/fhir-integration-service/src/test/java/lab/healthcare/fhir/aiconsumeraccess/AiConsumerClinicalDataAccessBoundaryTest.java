package lab.healthcare.fhir.aiconsumeraccess;

import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
import lab.healthcare.fhir.aiconsumer.AiConsumerContract;
import lab.healthcare.fhir.aiconsumer.AiConsumerContractService;
import lab.healthcare.fhir.aiconsumerauthorization.AiConsumerAuthorizationBoundary;
import lab.healthcare.fhir.aiconsumerconsent.AiConsumerConsentBoundary;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerIdentity;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicy;
import lab.healthcare.fhir.aiconsumerpolicy.AiConsumerPolicyInput;
import lab.healthcare.fhir.aiconsumerreadiness.AiConsumerReadiness;
import lab.healthcare.fhir.aiconsumerscope.AiConsumerDataScopeBoundary;
import lab.healthcare.fhir.aiconsumerscope.AiConsumerDataScopeResult;
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

class AiConsumerClinicalDataAccessBoundaryTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T23:30:00Z");

    @Test
    void validScopeWithoutAccessProviderIsNotGranted() {
        AiConsumerClinicalDataAccessResult result = AiConsumerClinicalDataAccessBoundary.evaluate(validScope());

        assertThat(result.status()).isEqualTo(AiConsumerClinicalDataAccessStatus.NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS);
        assertThat(result.reason()).isEqualTo(AiConsumerClinicalDataAccessReasonCodes.SCOPE_NOT_PREPARED);
        assertThat(result.accessRequestDeclared()).isFalse();
        assertThat(result.accessRequestEvaluated()).isFalse();
        assertThat(result.scopeReferencePresent()).isFalse();
        assertThat(result.realAuthorizationRequired()).isTrue();
        assertThat(result.clinicalDataAccessRequested()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void missingDataScopeResultIsBlocked() {
        AiConsumerClinicalDataAccessResult result =
                AiConsumerClinicalDataAccessBoundary.evaluate((AiConsumerDataScopeResult) null);

        assertThat(result.status()).isEqualTo(AiConsumerClinicalDataAccessStatus.ACCESS_REQUEST_BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerClinicalDataAccessReasonCodes.MISSING_DATA_SCOPE_RESULT);
        assertSafeInvariants(result);
    }

    @Test
    void unevaluatedScopeCannotGrantAccess() {
        AiConsumerClinicalDataAccessResult result = AiConsumerClinicalDataAccessBoundary.evaluate(validScope());

        assertThat(result.scopeEvaluated()).isFalse();
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertThat(result.clinicalDataAccessAllowed()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void unapprovedScopeKeepsAccessBlocked() {
        AiConsumerClinicalDataAccessResult result = AiConsumerClinicalDataAccessBoundary.evaluate(validScope());

        assertThat(result.clinicalDataScopeApprovalAvailable()).isFalse();
        assertThat(result.status()).isEqualTo(AiConsumerClinicalDataAccessStatus.NOT_GRANTED_FOR_CLINICAL_DATA_ACCESS);
        assertSafeInvariants(result);
    }

    @Test
    void missingRequestDeclarationIsNotDeclared() {
        AiConsumerClinicalDataAccessResult result = AiConsumerClinicalDataAccessBoundary.evaluate(
                validScope(),
                ClinicalDataAccessRequestContext.laboratory().withDeclarationAttempted(true));

        assertThat(result.status()).isEqualTo(AiConsumerClinicalDataAccessStatus.ACCESS_REQUEST_NOT_DECLARED);
        assertThat(result.reason()).isEqualTo(AiConsumerClinicalDataAccessReasonCodes.ACCESS_REQUEST_NOT_DECLARED);
        assertThat(result.accessRequestDeclared()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void syntheticDeclaredRequestIsNotEvaluatedOrGranted() {
        AiConsumerClinicalDataAccessResult result = AiConsumerClinicalDataAccessBoundary.evaluate(
                validScope(),
                ClinicalDataAccessRequestContext.laboratory()
                        .withRequestDeclared(true)
                        .withScopeReferencePresent(true));

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataAccessStatus.ACCESS_REQUEST_DECLARED_NOT_EVALUATED);
        assertThat(result.accessRequestDeclared()).isTrue();
        assertThat(result.accessRequestEvaluated()).isFalse();
        assertThat(result.clinicalDataAccessRequested()).isFalse();
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertThat(result.clinicalDataAccessAllowed()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void declaredRequestWithoutScopeRequiresScope() {
        AiConsumerClinicalDataAccessResult result = AiConsumerClinicalDataAccessBoundary.evaluate(
                validScope(), ClinicalDataAccessRequestContext.laboratory().withRequestDeclared(true));

        assertThat(result.status()).isEqualTo(AiConsumerClinicalDataAccessStatus.ACCESS_REQUEST_REQUIRES_SCOPE);
        assertThat(result.reason()).isEqualTo(AiConsumerClinicalDataAccessReasonCodes.ACCESS_REQUEST_REQUIRES_SCOPE);
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertThat(result.clinicalDataAccessAllowed()).isFalse();
        assertDeniedAccess(result);
    }

    @Test
    void effectiveSyntheticRequestIsNotGranted() {
        AiConsumerClinicalDataAccessResult result = AiConsumerClinicalDataAccessBoundary.evaluate(
                validScope(),
                ClinicalDataAccessRequestContext.laboratory()
                        .withEffectiveRequestClaim(true)
                        .withScopeReferencePresent(true));

        assertThat(result.status())
                .isEqualTo(AiConsumerClinicalDataAccessStatus.ACCESS_REQUEST_REQUIRES_REAL_AUTHORIZATION);
        assertThat(result.clinicalDataAccessRequested()).isTrue();
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertThat(result.clinicalDataAccessAllowed()).isFalse();
        assertDeniedAccess(result);
    }

    @Test
    void realAuthorizationRemainsRequired() {
        AiConsumerClinicalDataAccessResult result = AiConsumerClinicalDataAccessBoundary.evaluate(validScope());

        assertThat(result.realAuthorizationRequired()).isTrue();
        assertThat(result.clinicalDataAccessAuthorizationAvailable()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void missingTenantScopeIsBlocked() {
        AiConsumerClinicalDataAccessResult result = AiConsumerClinicalDataAccessBoundary.evaluate(
                validScope(), ClinicalDataAccessRequestContext.laboratory().withTenantScopePresent(false));

        assertThat(result.status()).isEqualTo(AiConsumerClinicalDataAccessStatus.ACCESS_REQUEST_BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerClinicalDataAccessReasonCodes.MISSING_TENANT_SCOPE);
        assertSafeInvariants(result);
    }

    @Test
    void manipulatedContextCannotGrantAccess() {
        AiConsumerClinicalDataAccessResult result = AiConsumerClinicalDataAccessBoundary.evaluate(
                validScope(),
                ClinicalDataAccessRequestContext.laboratory()
                        .withGrantedClaim(true)
                        .withAllowedClaim(true)
                        .withEvaluatedClaim(true));

        assertThat(result.status()).isEqualTo(AiConsumerClinicalDataAccessStatus.ACCESS_REQUEST_BLOCKED);
        assertThat(result.reason()).isEqualTo(AiConsumerClinicalDataAccessReasonCodes.UNTRUSTED_ACCESS_ASSERTION);
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertThat(result.clinicalDataAccessAllowed()).isFalse();
        assertThat(result.accessRequestEvaluated()).isFalse();
        assertSafeInvariants(result);
    }

    @Test
    void evaluationIsDeterministicAndHasNoClinicalPayload() {
        AiConsumerClinicalDataAccessResult first = AiConsumerClinicalDataAccessBoundary.evaluate(validScope());
        AiConsumerClinicalDataAccessResult second = AiConsumerClinicalDataAccessBoundary.evaluate(validScope());

        assertThat(first).isEqualTo(second);
        assertThat(first.requestedDataCategories()).isEmpty();
        assertThat(first.requestedResourceTypes()).isEmpty();
        assertThat(first.toString()).doesNotContain("access_token");
        assertThat(first.toString()).doesNotContain("Patient/");
        assertThat(first.toString()).doesNotContain("\"resourceType\"");
        assertSafeInvariants(first);
    }

    private static void assertSafeInvariants(AiConsumerClinicalDataAccessResult result) {
        assertThat(result.clinicalDataAccessRequested()).isFalse();
        assertDeniedAccess(result);
    }

    private static void assertDeniedAccess(AiConsumerClinicalDataAccessResult result) {
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.processingStatus()).isEqualTo(AiConsumerClinicalDataAccessResult.NOT_EXECUTED);
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerClinicalDataAccessResult.NOT_DISPATCHED);
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
        assertThat(result.clinicalDataAccessGranted()).isFalse();
        assertThat(result.accessRequestEvaluated()).isFalse();
        assertThat(result.clinicalDataAccessGrantAvailable()).isFalse();
        assertThat(result.clinicalDataAccessEnforced()).isFalse();
        assertThat(result.clinicalDataAccessProviderConfigured()).isFalse();
        assertThat(result.clinicalDataAccessAuthorizationAvailable()).isFalse();
        assertThat(result.realAuthorizationRequired()).isTrue();
    }

    private static AiConsumerDataScopeResult validScope() {
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
