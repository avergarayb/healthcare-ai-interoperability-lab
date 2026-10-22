package lab.healthcare.fhir.interop;

import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Typed catalogue of external systems. Adding a system is a configuration entry
 * plus, when it must be read, its own connector. This registry does not open
 * connections and does not federate clinical reads.
 */
@Component
public class SourceRegistry {

    public static final Set<String> CAPABILITIES = Set.of(
            "patient",
            "encounter",
            "observation",
            "appointment",
            "service-request",
            "diagnostic-report");

    private static final Pattern KEY = Pattern.compile("[a-z0-9\\-]{1,64}");

    private final List<SourceDescriptor> sources;

    public SourceRegistry(InteropSourcesProperties properties) {
        List<SourceDescriptor> declared = new ArrayList<>();
        properties.getSources().forEach((key, value) -> declared.add(descriptor(key, value)));
        this.sources = List.copyOf(declared);
    }

    public List<SourceDescriptor> sources() {
        return sources;
    }

    public java.util.Optional<SourceDescriptor> find(String key) {
        return sources.stream().filter(source -> source.key().equals(key)).findFirst();
    }

    private static SourceDescriptor descriptor(String key, InteropSourcesProperties.SourceProperties value) {
        if (key == null || !KEY.matcher(key).matches() || value == null) {
            throw new IllegalStateException("Interop source key is invalid");
        }
        if (value.getOrganizationId() == null || value.getOrganizationId().isBlank()) {
            throw new IllegalStateException("Interop source organization is required");
        }
        if (value.getDisplayName() == null || value.getDisplayName().isBlank()) {
            throw new IllegalStateException("Interop source display name is required");
        }
        if (value.getBaseUrl() == null || value.getBaseUrl().isBlank()) {
            throw new IllegalStateException("Interop source base URL is required");
        }
        if (value.getCapabilities().isEmpty()) {
            throw new IllegalStateException("Interop source capabilities are required");
        }
        for (String capability : value.getCapabilities()) {
            if (!CAPABILITIES.contains(capability)) {
                throw new IllegalStateException("Interop source capability is unknown");
            }
        }
        return new SourceDescriptor(
                key,
                value.getOrganizationId().trim(),
                value.getDisplayName().trim(),
                value.getBaseUrl().trim(),
                List.copyOf(value.getCapabilities()));
    }

    public record SourceDescriptor(
            String key,
            String organizationId,
            String displayName,
            String baseUrl,
            List<String> capabilities) {
    }
}
