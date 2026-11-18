package lab.healthcare.fhir.exchange;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

final class MllpSession {

    static final int MAX_BYTES = 64 * 1024;

    private MllpSession() {
    }

    static boolean containerName(String host) {
        return host != null && host.matches("[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?");
    }

    static boolean loopback(String host) {
        try {
            if (host == null) {
                return false;
            }
            if ("localhost".equalsIgnoreCase(host)) {
                return true;
            }
            return InetAddress.getByName(host).isLoopbackAddress();
        } catch (Exception ex) {
            return false;
        }
    }

    static ServerSocket listen(int port) throws IOException {
        return listen(port, false);
    }

    static ServerSocket listen(int port, boolean containerNetwork) throws IOException {
        ServerSocket server = new ServerSocket();
        InetAddress address = containerNetwork
                ? InetAddress.getByName("0.0.0.0")
                : InetAddress.getLoopbackAddress();
        server.bind(new InetSocketAddress(address, port));
        return server;
    }

    static String transact(String host, int port, String message, Duration connectTimeout, Duration readTimeout) throws IOException {
        return transact(host, port, message, connectTimeout, readTimeout, false);
    }

    static String transact(
            String host, int port, String message, Duration connectTimeout, Duration readTimeout, boolean containerNetwork)
            throws IOException {
        if (!containerNetwork && !loopback(host)) {
            throw new IOException("MLLP peer is not a loopback address");
        }
        if (containerNetwork && !containerName(host)) {
            throw new IOException("MLLP peer is not a container service name");
        }
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress(host, port), (int) connectTimeout.toMillis());
            socket.setSoTimeout((int) readTimeout.toMillis());
            write(socket.getOutputStream(), message);
            return read(socket.getInputStream());
        }
    }

    static void write(OutputStream output, String message) throws IOException {
        output.write(0x0b);
        output.write(message.getBytes(StandardCharsets.UTF_8));
        output.write(0x1c);
        output.write(0x0d);
        output.flush();
    }

    static String read(InputStream input) throws IOException {
        int marker = input.read();
        while (marker != -1 && marker != 0x0b) {
            marker = input.read();
        }
        if (marker != 0x0b) {
            throw new IOException("MLLP start block is missing");
        }
        ByteArrayOutputStream body = new ByteArrayOutputStream();
        int current;
        while ((current = input.read()) != -1) {
            if (current == 0x1c) {
                if (input.read() != 0x0d) {
                    throw new IOException("MLLP end block is incomplete");
                }
                break;
            }
            body.write(current);
            if (body.size() > MAX_BYTES) {
                throw new IOException("MLLP message is too large");
            }
        }
        return body.toString(StandardCharsets.UTF_8);
    }
}
