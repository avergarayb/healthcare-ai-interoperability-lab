package lab.healthcare.fhir.externalfhir;

import lab.healthcare.fhir.interop.SourceRegistry.SourceDescriptor;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.net.URI;
import java.util.List;

/**
 * Closed allowlist for one external FHIR R4 reader. Disabled by default.
 * A browser parameter or a model argument cannot change the host.
 */
@ConfigurationProperties(prefix = "external-fhir")
public class ExternalFhirProperties {

    public static final String SOURCE_KEY = "smart-sandbox";
    public static final String ORGANIZATION_ID = "org-smart-sandbox";
    public static final String ALLOWED_HOST = "r4.smarthealthit.org";
    public static final String BASE_URL = "https://r4.smarthealthit.org";

    private boolean enabled;
    private String sourceKey = SOURCE_KEY;
    private String organizationId = ORGANIZATION_ID;
    private String displayName = "SMART Health IT R4 sandbox";
    private String baseUrl = BASE_URL;
    private String allowedHost = ALLOWED_HOST;
    private String callerSystem = "mini-his";
    private int connectTimeoutMillis = 2000;
    private int readTimeoutMillis = 8000;
    private int maxBytes = 1_048_576;
    private int maxPages = 2;
    private int pageSize = 20;
    private String linkStorePath = "";
    private String auditStorePath = "";

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public String getSourceKey() {
        return sourceKey;
    }

    public void setSourceKey(String sourceKey) {
        this.sourceKey = sourceKey;
    }

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

    public String getAllowedHost() {
        return allowedHost;
    }

    public void setAllowedHost(String allowedHost) {
        this.allowedHost = allowedHost;
    }

    public String getCallerSystem() {
        return callerSystem;
    }

    public void setCallerSystem(String callerSystem) {
        this.callerSystem = callerSystem;
    }

    public int getConnectTimeoutMillis() {
        return connectTimeoutMillis;
    }

    public void setConnectTimeoutMillis(int connectTimeoutMillis) {
        this.connectTimeoutMillis = connectTimeoutMillis;
    }

    public int getReadTimeoutMillis() {
        return readTimeoutMillis;
    }

    public void setReadTimeoutMillis(int readTimeoutMillis) {
        this.readTimeoutMillis = readTimeoutMillis;
    }

    public int getMaxBytes() {
        return maxBytes;
    }

    public void setMaxBytes(int maxBytes) {
        this.maxBytes = maxBytes;
    }

    public int getMaxPages() {
        return maxPages;
    }

    public void setMaxPages(int maxPages) {
        this.maxPages = maxPages;
    }

    public int getPageSize() {
        return pageSize;
    }

    public void setPageSize(int pageSize) {
        this.pageSize = pageSize;
    }

    public String getLinkStorePath() {
        return linkStorePath;
    }

    public void setLinkStorePath(String linkStorePath) {
        this.linkStorePath = linkStorePath == null ? "" : linkStorePath;
    }

    public String getAuditStorePath() {
        return auditStorePath;
    }

    public void setAuditStorePath(String auditStorePath) {
        this.auditStorePath = auditStorePath == null ? "" : auditStorePath;
    }

    public SourceDescriptor descriptor() {
        requireClosed();
        return new SourceDescriptor(
                sourceKey, organizationId, displayName, baseUrl,
                List.of("patient", "observation", "diagnostic-report"));
    }

    public void requireClosed() {
        if (!enabled) {
            return;
        }
        URI uri = URI.create(baseUrl);
        if (!"https".equals(uri.getScheme()) || uri.getUserInfo() != null || uri.getQuery() != null
                || uri.getFragment() != null || uri.getPort() != -1
                || !allowedHost.equals(uri.getHost()) || !ALLOWED_HOST.equals(allowedHost)
                || !SOURCE_KEY.equals(sourceKey) || !ORGANIZATION_ID.equals(organizationId)
                || !"mini-his".equals(callerSystem)
                || connectTimeoutMillis <= 0 || readTimeoutMillis <= 0
                || maxBytes < 1024 || maxBytes > 1_048_576
                || maxPages < 1 || maxPages > 2 || pageSize < 1 || pageSize > 20) {
            throw new IllegalStateException("external fhir configuration is not acceptable");
        }
    }
}
