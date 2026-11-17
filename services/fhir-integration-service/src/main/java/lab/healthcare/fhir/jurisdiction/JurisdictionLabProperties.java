package lab.healthcare.fhir.jurisdiction;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * One process selects one demonstration profile. The browser does not choose it.
 */
@ConfigurationProperties(prefix = "jurisdiction-lab")
public class JurisdictionLabProperties {

    private boolean enabled;
    private String profile = "";

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public String getProfile() {
        return profile;
    }

    public void setProfile(String profile) {
        this.profile = profile == null ? "" : profile.trim();
    }
}
