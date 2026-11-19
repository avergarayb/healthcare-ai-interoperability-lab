package lab.healthcare.minilis;

import org.junit.jupiter.api.Test;

import java.net.URI;

import static org.junit.jupiter.api.Assertions.assertEquals;

class BenchOidcClaimsTest {

    @Test
    void anIssuerUrlMatchesTheConfiguredString() throws Exception {
        assertEquals(
                "http://127.0.0.1:18340/realms/hospital-lab",
                BenchSecurityConfiguration.issuerOf(URI.create("http://127.0.0.1:18340/realms/hospital-lab").toURL()));
        assertEquals(
                "http://127.0.0.1:18340/realms/hospital-lab",
                BenchSecurityConfiguration.issuerOf("http://127.0.0.1:18340/realms/hospital-lab"));
        assertEquals("", BenchSecurityConfiguration.issuerOf(null));
    }
}
