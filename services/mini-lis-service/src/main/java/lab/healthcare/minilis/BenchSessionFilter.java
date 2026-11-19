package lab.healthcare.minilis;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;

import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

@Component
@Order(2)
class BenchSessionFilter extends OncePerRequestFilter {

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return path == null
                || !(path.equals("/bench") || path.startsWith("/bench/"))
                || path.equals("/bench/login")
                || path.equals("/bench/app.css");
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        HttpSession session = request.getSession(false);
        Object principal = session == null ? null : session.getAttribute("benchPrincipal");
        if (!(principal instanceof BenchController.BenchPrincipal bench)
                || !"org-mini-his".equals(bench.organizationId())) {
            response.sendRedirect("/bench/login?aviso=sesion");
            return;
        }
        filterChain.doFilter(request, response);
    }
}
