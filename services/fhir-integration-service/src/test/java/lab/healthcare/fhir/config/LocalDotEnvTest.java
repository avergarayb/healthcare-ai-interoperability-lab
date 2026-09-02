package lab.healthcare.fhir.config;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class LocalDotEnvTest {

    @Test
    void applyIgnoresCommentsAndDoesNotOverrideExistingProperty() {
        String key = "ORACLE_HEALTH_SANDBOX_CLIENT_ID";
        String previous = System.getProperty(key);
        try {
            System.setProperty(key, "already-set");
            LocalDotEnv.apply("# comment");
            LocalDotEnv.apply(key + "=from-file");
            assertThat(System.getProperty(key)).isEqualTo("already-set");
        } finally {
            if (previous == null) {
                System.clearProperty(key);
            } else {
                System.setProperty(key, previous);
            }
        }
    }

    @Test
    void applySetsBlankPropertyFromPlaceholderLine() {
        String key = "ORACLE_HEALTH_SANDBOX_SCOPE";
        String previous = System.getProperty(key);
        try {
            System.clearProperty(key);
            LocalDotEnv.apply(key + "=");
            assertThat(System.getProperty(key)).isEmpty();
        } finally {
            if (previous == null) {
                System.clearProperty(key);
            } else {
                System.setProperty(key, previous);
            }
        }
    }
}
