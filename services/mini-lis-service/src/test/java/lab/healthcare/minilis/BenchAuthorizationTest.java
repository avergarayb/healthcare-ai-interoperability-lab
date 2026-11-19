package lab.healthcare.minilis;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class BenchAuthorizationTest {
    @Test
    void publicationValidationAndAuditStaySeparated() {
        assertThat(BenchAuthorization.permits("lab-technician", "org-mini-his", "publish")).isFalse();
        assertThat(BenchAuthorization.permits("lab-technician", "org-mini-his", "validate")).isFalse();
        assertThat(BenchAuthorization.permits("receptionist", "org-mini-his", "validate")).isFalse();
        assertThat(BenchAuthorization.permits("receptionist", "org-mini-his", "receive")).isTrue();
        assertThat(BenchAuthorization.permits("lab-validator", "org-mini-his", "publish")).isTrue();
        assertThat(BenchAuthorization.permits("auditor", "org-mini-his", "draft")).isFalse();
        assertThat(BenchAuthorization.permits("lab-validator", "org-pe-lab-demo", "publish")).isFalse();
        assertThat(BenchAuthorization.permits("clinician", "org-mini-his", "publish")).isFalse();
    }
}
