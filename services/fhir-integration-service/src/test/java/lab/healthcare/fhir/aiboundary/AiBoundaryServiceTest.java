package lab.healthcare.fhir.aiboundary;

import lab.healthcare.fhir.agent.AgentDecision;
import lab.healthcare.fhir.agent.AgentReasonCodes;
import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.modelboundary.BoundaryCollection;
import lab.healthcare.fhir.modelboundary.BoundaryCondition;
import lab.healthcare.fhir.modelboundary.BoundaryDiagnosticReport;
import lab.healthcare.fhir.modelboundary.BoundaryMedicationRequest;
import lab.healthcare.fhir.modelboundary.BoundaryObservation;
import lab.healthcare.fhir.modelboundary.BoundaryPatient;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractVersion;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.pipeline.PipelineDiagnoses;
import lab.healthcare.fhir.pipeline.PipelineDiagnosis;
import lab.healthcare.fhir.pipeline.PipelineStageStatus;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AiBoundaryServiceTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T21:30:00Z");

    @Test
    void readyDoesNotAuthorizeAModelCall() {
        AiBoundaryResult result = prepare(completeOracle());

        assertThat(result.decision().agentDecision()).isEqualTo(AgentDecision.READY);
        assertThat(result.decision().pipelineStatus()).isEqualTo(PipelineStageStatus.SUCCESS);
        assertThat(result.decision().clinicalDataAvailable()).isTrue();
        assertThat(result.decision().requiresHumanReview()).isTrue();
        assertThat(result.decision().modelCalled()).isFalse();
        assertThat(result.decision().modelCallAuthorized()).isFalse();
        assertThat(result.reasonCode()).isEqualTo(AgentReasonCodes.READY_FOR_BOUNDARY);
        assertThat(result.toString()).doesNotContain("active");
        assertThat(result.toString()).doesNotContain("access_token");
    }

    @Test
    void blockedDecisionIsPreserved() {
        AiBoundaryResult result = prepare(new ModelBoundaryContract(
                "v2",
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                null,
                null,
                null,
                null,
                null));

        assertThat(result.decision().agentDecision()).isEqualTo(AgentDecision.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AgentReasonCodes.CONTRACT_REJECTED);
        assertThat(result.decision().modelCallAuthorized()).isFalse();
        assertThat(result.decision().clinicalDataAvailable()).isFalse();
        assertThat(result.decision().requiresHumanReview()).isTrue();
    }

    @Test
    void humanReviewIsPreservedAndDoesNotAuthorizeAModel() {
        AiBoundaryResult result = prepare(emptyClinicalData());

        assertThat(result.decision().agentDecision()).isEqualTo(AgentDecision.REQUIRES_HUMAN_REVIEW);
        assertThat(result.reasonCode()).isEqualTo(AgentReasonCodes.INSUFFICIENT_CLINICAL_DATA);
        assertThat(result.decision().clinicalDataAvailable()).isFalse();
        assertThat(result.decision().requiresHumanReview()).isTrue();
        assertThat(result.decision().modelCallAuthorized()).isFalse();
        assertThat(result.toString()).doesNotContain("active");
    }

    @Test
    void partialPipelineIsPreserved() {
        AiBoundaryResult result = prepare(partialTimeout());

        assertThat(result.decision().pipelineStatus()).isEqualTo(PipelineStageStatus.PARTIAL);
        assertThat(result.decision().agentDecision()).isEqualTo(AgentDecision.REQUIRES_HUMAN_REVIEW);
        assertThat(result.warnings()).contains("timeout:observations", "not-requested:medicationRequests");
        assertThat(result.decision().modelCallAuthorized()).isFalse();
        assertThat(result.medicationRequestsStatus()).isEqualTo("NOT_REQUESTED");
    }

    @Test
    void operationalWarningsArePreserved() {
        AiBoundaryResult result = prepare(truncatedOracle());

        assertThat(result.decision().agentDecision()).isEqualTo(AgentDecision.READY);
        assertThat(result.warnings()).contains("truncated:conditions");
        assertThat(result.medicationRequestsStatus()).isEqualTo("SUCCESS");
        assertThat(result.decision().modelCalled()).isFalse();
        assertThat(result.decision().modelCallAuthorized()).isFalse();
    }

    @Test
    void mapperDoesNotRecomputeAReadyDecision() {
        DeterministicAgentResult injected = new DeterministicAgentResult(
                AgentDecision.READY,
                AgentReasonCodes.READY_FOR_BOUNDARY,
                List.of(),
                List.of("not-requested:medicationRequests"),
                true,
                false,
                PipelineStageStatus.SUCCESS,
                true,
                true);
        ModelBoundaryContract contract = completeEpic();
        AiBoundaryResult result = AiBoundaryService.prepare(
                AiBoundaryInput.of(contract, PipelineDiagnoses.fromContract(contract), injected),
                "corr-058");

        assertThat(result.decision().agentDecision()).isEqualTo(AgentDecision.READY);
        assertThat(result.warnings()).containsExactly("not-requested:medicationRequests");
        assertThat(result.medicationRequestsStatus()).isEqualTo("NOT_REQUESTED");
        assertThat(result.correlationId()).isEqualTo("corr-058");
        assertThat(result.decision().modelCallAuthorized()).isFalse();
    }

    @Test
    void missingInputIsRejected() {
        assertThatThrownBy(() -> AiBoundaryService.prepare(null)).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> AiBoundaryInput.of(completeOracle(), null, null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    private static AiBoundaryResult prepare(ModelBoundaryContract contract) {
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(contract);
        DeterministicAgentResult agent = DeterministicAgent.evaluate(DeterministicAgentInput.of(contract, diagnosis));
        return AiBoundaryService.prepare(AiBoundaryInput.of(contract, diagnosis, agent), "corr-lab");
    }

    private static ModelBoundaryContract completeOracle() {
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "oracle-health-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                collection(new BoundaryCondition("Condition", "active")),
                collection(new BoundaryObservation("Observation", "final")),
                collection(new BoundaryDiagnosticReport("DiagnosticReport", "final")),
                collection(new BoundaryMedicationRequest("MedicationRequest", "active", "order")));
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

    private static ModelBoundaryContract partialTimeout() {
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                collection(new BoundaryCondition("Condition", "active")),
                new BoundaryCollection<>(ClinicalSnapshotResourceStatus.TIMEOUT, null, null, null, List.of()),
                collection(new BoundaryDiagnosticReport("DiagnosticReport", "final")),
                null);
    }

    private static ModelBoundaryContract truncatedOracle() {
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "oracle-health-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        8,
                        5,
                        true,
                        List.of(
                                new BoundaryCondition("Condition", "active"),
                                new BoundaryCondition("Condition", "active"),
                                new BoundaryCondition("Condition", "active"),
                                new BoundaryCondition("Condition", "active"),
                                new BoundaryCondition("Condition", "active"))),
                collection(new BoundaryObservation("Observation", "final")),
                collection(new BoundaryDiagnosticReport("DiagnosticReport", "final")),
                collection(new BoundaryMedicationRequest("MedicationRequest", "active", "order")));
    }

    private static <T> BoundaryCollection<T> collection(T record) {
        return new BoundaryCollection<>(ClinicalSnapshotResourceStatus.SUCCESS, 1, 1, false, List.of(record));
    }
}
