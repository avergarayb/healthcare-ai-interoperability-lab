package lab.healthcare.minilis;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;
import java.util.Arrays;
import java.util.List;

@ConfigurationProperties(prefix = "mini-lis.hl7")
public class Hl7Properties {

    private boolean enabled;
    private String bindAddress = "127.0.0.1";
    private int port = 2575;
    private String sharedSecret = "";
    private String sendingApplication = "FHIR-EXCHANGE";
    private String sendingFacility = "fhir-integration-service";
    private String receivingApplication = "MINI-LIS";
    private String receivingFacility = "org-mini-lis";
    private String allowedOrganizations = "org-mini-his";
    private String outboundHost = "127.0.0.1";
    private int outboundPort;
    private Duration connectTimeout = Duration.ofSeconds(2);
    private Duration readTimeout = Duration.ofSeconds(5);

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public String getBindAddress() {
        return bindAddress;
    }

    public void setBindAddress(String bindAddress) {
        this.bindAddress = bindAddress;
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

    public String getAllowedOrganizations() {
        return allowedOrganizations;
    }

    public void setAllowedOrganizations(String allowedOrganizations) {
        this.allowedOrganizations = allowedOrganizations == null ? "" : allowedOrganizations;
    }

    public List<String> allowedOrganizationList() {
        return Arrays.stream(allowedOrganizations.split(",")).map(String::trim).filter(value -> !value.isEmpty()).toList();
    }

    public String getOutboundHost() {
        return outboundHost;
    }

    public void setOutboundHost(String outboundHost) {
        this.outboundHost = outboundHost;
    }

    public int getOutboundPort() {
        return outboundPort;
    }

    public void setOutboundPort(int outboundPort) {
        this.outboundPort = outboundPort;
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
}
