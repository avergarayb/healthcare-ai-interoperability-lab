package lab.healthcare.fhir.interop;

import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
public class InteropSourceController {

    private final SourceRegistry registry;

    public InteropSourceController(SourceRegistry registry) {
        this.registry = registry;
    }

    @GetMapping(path = "/api/interop/v1/sources", produces = MediaType.APPLICATION_JSON_VALUE)
    public SourceList sources() {
        List<SourceView> views = registry.sources().stream()
                .map(source -> new SourceView(
                        source.key(),
                        source.organizationId(),
                        source.displayName(),
                        source.capabilities(),
                        "mini-his".equals(source.key()) || "mini-lis".equals(source.key())
                                ? "installed"
                                : "declared"))
                .toList();
        return new SourceList(views);
    }

    public record SourceList(List<SourceView> sources) {
    }

    public record SourceView(
            String key,
            String organizationId,
            String displayName,
            List<String> capabilities,
            String connector) {
    }
}
