package lab.healthcare.fhir.federation;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@ConfigurationProperties(prefix = "federation")
public class FederationProperties {

    private int maxSources = 4;
    private int maxEntries = 100;
    private int queryBudgetSeconds = 20;
    private Map<String, Participant> participants = new LinkedHashMap<>();
    private Map<String, List<String>> grants = new LinkedHashMap<>();

    public int getMaxSources() {
        return maxSources;
    }

    public void setMaxSources(int maxSources) {
        this.maxSources = maxSources;
    }

    public int getMaxEntries() {
        return maxEntries;
    }

    public void setMaxEntries(int maxEntries) {
        this.maxEntries = maxEntries;
    }

    public int getQueryBudgetSeconds() {
        return queryBudgetSeconds;
    }

    public void setQueryBudgetSeconds(int queryBudgetSeconds) {
        this.queryBudgetSeconds = queryBudgetSeconds;
    }

    public Map<String, Participant> getParticipants() {
        return participants;
    }

    public void setParticipants(Map<String, Participant> participants) {
        this.participants = participants == null ? new LinkedHashMap<>() : participants;
    }

    public Map<String, List<String>> getGrants() {
        return grants;
    }

    public void setGrants(Map<String, List<String>> grants) {
        this.grants = grants == null ? new LinkedHashMap<>() : grants;
    }

    public static class Participant {
        private String serviceToken = "";

        public String getServiceToken() {
            return serviceToken;
        }

        public void setServiceToken(String serviceToken) {
            this.serviceToken = serviceToken == null ? "" : serviceToken;
        }
    }
}
