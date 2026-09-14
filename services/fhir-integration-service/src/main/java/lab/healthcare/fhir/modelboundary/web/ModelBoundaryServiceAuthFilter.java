package lab.healthcare.fhir.modelboundary.web;

import lab.healthcare.fhir.modelboundary.ModelBoundaryServiceTokenSettings;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * Rejects unauthenticated access to {@code GET /api/model-boundary/v1} before
 * the controller runs. Does not invoke {@code currentContract()}.
 */
public class ModelBoundaryServiceAuthFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(ModelBoundaryServiceAuthFilter.class);

    private final ModelBoundaryServiceTokenSettings settings;

    public ModelBoundaryServiceAuthFilter(ModelBoundaryServiceTokenSettings settings) {
        if (settings == null) {
            throw new IllegalArgumentException("Service token settings must be provided");
        }
        this.settings = settings;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return request.getMethod() == null || !"GET".equalsIgnoreCase(request.getMethod());
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        String presented = request.getHeader(ModelBoundaryServiceTokenSettings.HEADER);
        if (settings.matches(presented)) {
            filterChain.doFilter(request, response);
            return;
        }
        String reason = !settings.configured()
                ? "unconfigured"
                : presented == null ? "absent" : presented.isBlank() ? "empty" : "mismatch";
        log.info("Model boundary service authentication rejected reason={}", reason);
        response.setStatus(HttpStatus.UNAUTHORIZED.value());
    }
}
