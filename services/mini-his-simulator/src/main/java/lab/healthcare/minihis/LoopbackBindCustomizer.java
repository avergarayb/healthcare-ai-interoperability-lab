package lab.healthcare.minihis;

import org.springframework.boot.web.server.ConfigurableWebServerFactory;
import org.springframework.boot.web.server.WebServerFactoryCustomizer;
import org.springframework.stereotype.Component;

import java.net.InetAddress;
import java.net.UnknownHostException;

@Component
public class LoopbackBindCustomizer implements WebServerFactoryCustomizer<ConfigurableWebServerFactory> {

    @Override
    public void customize(ConfigurableWebServerFactory factory) {
        try {
            factory.setAddress(InetAddress.getByName(LoopbackGuard.BIND_ADDRESS));
        } catch (UnknownHostException ex) {
            throw new IllegalStateException("Loopback address is unavailable", ex);
        }
    }
}
