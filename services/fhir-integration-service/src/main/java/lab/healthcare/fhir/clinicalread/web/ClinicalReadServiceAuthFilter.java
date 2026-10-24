package lab.healthcare.fhir.clinicalread.web;

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
import java.util.Enumeration;

/**
 * Rejects unauthenticated access to {@code /api/clinical-read/v1} with the
 * same shared secret as Model Boundary v1. The token value is never logged.
 */
public class ClinicalReadServiceAuthFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(ClinicalReadServiceAuthFilter.class);

    private final ModelBoundaryServiceTokenSettings settings;

    public ClinicalReadServiceAuthFilter(ModelBoundaryServiceTokenSettings settings) {
        if (settings == null) {
            throw new IllegalArgumentException("Service token settings must be provided");
        }
        this.settings = settings;
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        Enumeration<String> values = request.getHeaders(ModelBoundaryServiceTokenSettings.HEADER);
        String presented = values != null && values.hasMoreElements() ? values.nextElement() : null;
        boolean duplicate = values != null && values.hasMoreElements();
        if (!duplicate && settings.matches(presented)) {
            filterChain.doFilter(request, response);
            return;
        }
        String reason = !settings.configured()
                ? "unconfigured"
                : duplicate ? "multiple" : presented == null ? "absent" : presented.isBlank() ? "empty" : "mismatch";
        log.info("Clinical read service authentication rejected reason={}", reason);
        response.setStatus(HttpStatus.UNAUTHORIZED.value());
    }
}
