package lab.healthcare.fhir.snapshot;

import lab.healthcare.fhir.exception.FhirClientException;

import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.server.exceptions.AuthenticationException;
import ca.uhn.fhir.rest.server.exceptions.ForbiddenOperationException;
import org.junit.jupiter.api.Test;

import java.net.SocketTimeoutException;

import static org.assertj.core.api.Assertions.assertThat;

class ClinicalSnapshotStatusesTest {

    @Test
    void maps403ToUnauthorizedAndOtherFailuresToFailed() {
        assertThat(ClinicalSnapshotStatuses.fromFailure(
                        FhirClientException.from(new ForbiddenOperationException("forbidden"))))
                .isEqualTo(ClinicalSnapshotResourceStatus.UNAUTHORIZED);
        assertThat(ClinicalSnapshotStatuses.fromFailure(
                        FhirClientException.from(new AuthenticationException())))
                .isEqualTo(ClinicalSnapshotResourceStatus.FAILED);
        assertThat(ClinicalSnapshotStatuses.fromFailure(
                        FhirClientException.from(new FhirClientConnectionException(
                                "timed out", new SocketTimeoutException("Read timed out")))))
                .isEqualTo(ClinicalSnapshotResourceStatus.FAILED);
    }
}
