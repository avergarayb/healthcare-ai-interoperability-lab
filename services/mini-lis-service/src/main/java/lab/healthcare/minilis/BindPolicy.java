package lab.healthcare.minilis;

import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

import java.net.InetAddress;

@Component
class BindPolicy implements ApplicationRunner {

    private final Environment environment;

    BindPolicy(Environment environment) {
        this.environment = environment;
    }

    @Override
    public void run(ApplicationArguments args) {
        String address = environment.getProperty("server.address", "127.0.0.1");
        boolean allowExternal = Boolean.parseBoolean(environment.getProperty("mini-lis.allow-external-bind", "false"));
        if (allowExternal || isLoopback(address)) {
            return;
        }
        throw new IllegalStateException("Mini LIS refuses a non-loopback bind without mini-lis.allow-external-bind");
    }

    static boolean isLoopback(String address) {
        if (address == null || address.isBlank()) {
            return false;
        }
        String trimmed = address.trim();
        if ("localhost".equalsIgnoreCase(trimmed)) {
            return true;
        }
        try {
            return InetAddress.getByName(trimmed).isLoopbackAddress();
        } catch (Exception ex) {
            return false;
        }
    }
}
