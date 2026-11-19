package lab.healthcare.minilis;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.web.servlet.ServletContextInitializer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

@Configuration
class AcceptanceTransport {
    @Bean
    @ConditionalOnProperty(name = "mini-lis.oidc.acceptance", havingValue = "true")
    ServletContextInitializer acceptanceCookie() {
        return context -> {
            context.getSessionCookieConfig().setSecure(true);
            context.getSessionCookieConfig().setHttpOnly(true);
        };
    }
}

@Component
@Order(0)
@ConditionalOnProperty(name = "mini-lis.oidc.acceptance", havingValue = "true")
class AcceptanceHttpsFilter extends OncePerRequestFilter {
    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return !(path.startsWith("/bench") || path.startsWith("/oauth2") || path.startsWith("/login"));
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        if (!"https".equalsIgnoreCase(request.getScheme())) {
            response.sendError(HttpServletResponse.SC_FORBIDDEN);
            return;
        }
        chain.doFilter(request, response);
    }
}
