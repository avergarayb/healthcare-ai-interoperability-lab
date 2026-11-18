package lab.healthcare.minihis;

import org.springframework.boot.web.server.ConfigurableWebServerFactory;
import org.springframework.boot.web.server.WebServerFactoryCustomizer;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

import java.net.InetAddress;
import java.net.UnknownHostException;

@Component
public class LoopbackBindCustomizer implements WebServerFactoryCustomizer<ConfigurableWebServerFactory> {

    private final Environment environment;

    public LoopbackBindCustomizer(Environment environment) {
        this.environment = environment;
    }

    @Override
    public void customize(ConfigurableWebServerFactory factory) {
        boolean containerBind = Boolean.parseBoolean(environment.getProperty("mini-his.allow-container-bind", "false"));
        try {
            factory.setAddress(InetAddress.getByName(containerBind ? "0.0.0.0" : LoopbackGuard.BIND_ADDRESS));
        } catch (UnknownHostException ex) {
            throw new IllegalStateException("Loopback address is unavailable", ex);
        }
    }
}
