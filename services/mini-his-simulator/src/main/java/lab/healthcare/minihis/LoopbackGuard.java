package lab.healthcare.minihis;

import java.net.InetAddress;

public final class LoopbackGuard {

    public static final String BIND_ADDRESS = "127.0.0.1";

    private LoopbackGuard() {
    }

    public static boolean isLoopback(String address) {
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
