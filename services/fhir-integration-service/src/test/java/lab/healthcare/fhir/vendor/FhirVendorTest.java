package lab.healthcare.fhir.vendor;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FhirVendorTest {

    @Test
    void parsesOracleHealthAndLeavesGenericUnchanged() {
        assertThat(FhirVendor.fromConfiguration(null)).isEqualTo(FhirVendor.GENERIC);
        assertThat(FhirVendor.fromConfiguration("EPIC")).isEqualTo(FhirVendor.EPIC);
        assertThat(FhirVendor.fromConfiguration("ORACLE_HEALTH")).isEqualTo(FhirVendor.ORACLE_HEALTH);
        assertThat(FhirVendor.fromConfiguration("oracle-health")).isEqualTo(FhirVendor.ORACLE_HEALTH);
    }

    @Test
    void rejectsUnknownVendor() {
        assertThatThrownBy(() -> FhirVendor.fromConfiguration("ACME"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("ACME");
    }
}
