package lab.healthcare.minihis;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

@Component
@Order(1)
public class WardSessionFilter extends OncePerRequestFilter {
    private final String organizationId;
    private final boolean oidcEnabled;
    private final SecurityEvents events;

    public WardSessionFilter(
            SecurityEvents events,
            @Value("${mini-his.organization-id}") String organizationId,
            @Value("${mini-his.oidc.enabled:false}") boolean oidcEnabled) {
        this.events = events;
        this.organizationId = organizationId;
        this.oidcEnabled = oidcEnabled;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        boolean ward = path.startsWith("/ward") && !"/ward/login".equals(path) && !path.startsWith("/ward/app.");
        boolean showcase = oidcEnabled && path.startsWith("/showcase");
        return !(ward || showcase);
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        HttpSession session = request.getSession(false);
        Object principal = session == null ? null : session.getAttribute("wardPrincipal");
        if (!(principal instanceof WardPrincipal ward) || !organizationId.equals(ward.organizationId())) {
            events.record("anonymous", "", organizationId, "access", request.getRequestURI(), "denied");
            response.sendRedirect("/ward/login?aviso=sesion");
            return;
        }
        chain.doFilter(request, response);
    }
}
