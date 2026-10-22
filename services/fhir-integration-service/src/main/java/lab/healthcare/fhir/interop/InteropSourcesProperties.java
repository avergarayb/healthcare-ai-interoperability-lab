package lab.healthcare.fhir.interop;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@ConfigurationProperties(prefix = "interop")
public class InteropSourcesProperties {

    private Map<String, SourceProperties> sources = new LinkedHashMap<>();

    public Map<String, SourceProperties> getSources() {
        return sources;
    }

    public void setSources(Map<String, SourceProperties> sources) {
        this.sources = sources == null ? new LinkedHashMap<>() : sources;
    }

    public static class SourceProperties {
        private String organizationId;
        private String displayName;
        private String baseUrl;
        private List<String> capabilities = new ArrayList<>();

        public String getOrganizationId() {
            return organizationId;
        }

        public void setOrganizationId(String organizationId) {
            this.organizationId = organizationId;
        }

        public String getDisplayName() {
            return displayName;
        }

        public void setDisplayName(String displayName) {
            this.displayName = displayName;
        }

        public String getBaseUrl() {
            return baseUrl;
        }

        public void setBaseUrl(String baseUrl) {
            this.baseUrl = baseUrl;
        }

        public List<String> getCapabilities() {
            return capabilities;
        }

        public void setCapabilities(List<String> capabilities) {
            this.capabilities = capabilities == null ? new ArrayList<>() : capabilities;
        }
    }
}
