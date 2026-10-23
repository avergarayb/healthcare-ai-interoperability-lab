package lab.healthcare.minilis;

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

/**
 * Minimal MLLP session. One HL7 message in, one ACK out, then the socket closes.
 * There is no TLS. Callers must keep the bind on loopback unless an operator
 * explicitly allows an external address.
 */
final class MllpExchange {

    static final int MAX_BYTES = 64 * 1024;

    private MllpExchange() {
    }

    static ServerSocket listen(String bindAddress, int port) throws IOException {
        if (!BindPolicy.isLoopback(bindAddress)) {
            throw new IOException("MLLP bind is not a loopback address");
        }
        ServerSocket server = new ServerSocket();
        server.bind(new InetSocketAddress(InetAddress.getByName(bindAddress), port));
        return server;
    }

    static String transact(String host, int port, String message, Duration connectTimeout, Duration readTimeout)
            throws IOException {
        if (!BindPolicy.isLoopback(host)) {
            throw new IOException("MLLP peer is not a loopback address");
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
                int trailer = input.read();
                if (trailer != 0x0d) {
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
