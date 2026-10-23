package lab.healthcare.fhir.exchange;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;

@ConfigurationProperties(prefix = "exchange")
public class ExchangeProperties {

    private String storePath = "";
    private Map<String, Participant> participants = new LinkedHashMap<>();
    private Map<String, Connector> connectors = new LinkedHashMap<>();

    public String getStorePath() {
        return storePath;
    }

    public void setStorePath(String storePath) {
        this.storePath = storePath == null ? "" : storePath;
    }

    public Map<String, Participant> getParticipants() {
        return participants;
    }

    public void setParticipants(Map<String, Participant> participants) {
        this.participants = participants == null ? new LinkedHashMap<>() : participants;
    }

    public Map<String, Connector> getConnectors() {
        return connectors;
    }

    public void setConnectors(Map<String, Connector> connectors) {
        this.connectors = connectors == null ? new LinkedHashMap<>() : connectors;
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

    public static class Connector {
        private String baseUrl = "";
        private String serviceToken = "";
        private String protocol = "rest";
        private Duration connectTimeout = Duration.ofSeconds(2);
        private Duration readTimeout = Duration.ofSeconds(5);
        private Hl7 hl7 = new Hl7();

        public String getBaseUrl() {
            return baseUrl;
        }

        public void setBaseUrl(String baseUrl) {
            this.baseUrl = baseUrl == null ? "" : baseUrl;
        }

        public String getServiceToken() {
            return serviceToken;
        }

        public void setServiceToken(String serviceToken) {
            this.serviceToken = serviceToken == null ? "" : serviceToken;
        }

        public String getProtocol() {
            return protocol;
        }

        public void setProtocol(String protocol) {
            this.protocol = protocol == null || protocol.isBlank() ? "rest" : protocol;
        }

        public Duration getConnectTimeout() {
            return connectTimeout;
        }

        public void setConnectTimeout(Duration connectTimeout) {
            this.connectTimeout = connectTimeout;
        }

        public Duration getReadTimeout() {
            return readTimeout;
        }

        public void setReadTimeout(Duration readTimeout) {
            this.readTimeout = readTimeout;
        }

        public Hl7 getHl7() {
            return hl7;
        }

        public void setHl7(Hl7 hl7) {
            this.hl7 = hl7 == null ? new Hl7() : hl7;
        }
    }

    public static class Hl7 {
        private String host = "127.0.0.1";
        private int port = 2575;
        private String sharedSecret = "";
        private int listenPort = 2576;
        private String sendingApplication = "FHIR-EXCHANGE";
        private String sendingFacility = "fhir-integration-service";
        private String receivingApplication = "MINI-LIS";
        private String receivingFacility = "org-mini-lis";

        public String getHost() {
            return host;
        }

        public void setHost(String host) {
            this.host = host;
        }

        public int getPort() {
            return port;
        }

        public void setPort(int port) {
            this.port = port;
        }

        public String getSharedSecret() {
            return sharedSecret;
        }

        public void setSharedSecret(String sharedSecret) {
            this.sharedSecret = sharedSecret == null ? "" : sharedSecret;
        }

        public int getListenPort() {
            return listenPort;
        }

        public void setListenPort(int listenPort) {
            this.listenPort = listenPort;
        }

        public String getSendingApplication() {
            return sendingApplication;
        }

        public void setSendingApplication(String sendingApplication) {
            this.sendingApplication = sendingApplication;
        }

        public String getSendingFacility() {
            return sendingFacility;
        }

        public void setSendingFacility(String sendingFacility) {
            this.sendingFacility = sendingFacility;
        }

        public String getReceivingApplication() {
            return receivingApplication;
        }

        public void setReceivingApplication(String receivingApplication) {
            this.receivingApplication = receivingApplication;
        }

        public String getReceivingFacility() {
            return receivingFacility;
        }

        public void setReceivingFacility(String receivingFacility) {
            this.receivingFacility = receivingFacility;
        }
    }
}
