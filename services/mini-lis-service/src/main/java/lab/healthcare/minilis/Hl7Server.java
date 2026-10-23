package lab.healthcare.minilis;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import jakarta.annotation.PreDestroy;

import java.net.ServerSocket;
import java.net.Socket;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Loopback MLLP listener. It starts only when mini-lis.hl7.enabled is true.
 */
@Component
public class Hl7Server {

    private static final Logger log = LoggerFactory.getLogger(Hl7Server.class);

    private final Hl7Properties properties;
    private final Hl7OrderReceiver receiver;
    private final boolean allowExternalBind;
    private ServerSocket server;
    private ExecutorService workers;
    private volatile boolean running;

    public Hl7Server(Hl7Properties properties, Hl7OrderReceiver receiver,
            @org.springframework.beans.factory.annotation.Value("${mini-lis.allow-external-bind:false}") boolean allowExternalBind) {
        this.properties = properties;
        this.receiver = receiver;
        this.allowExternalBind = allowExternalBind;
    }

    @jakarta.annotation.PostConstruct
    public void start() {
        if (!properties.isEnabled()) {
            return;
        }
        if (!allowExternalBind && !BindPolicy.isLoopback(properties.getBindAddress())) {
            throw new IllegalStateException("Mini LIS HL7 refuses a non-loopback bind");
        }
        try {
            server = MllpExchange.listen(properties.getBindAddress(), properties.getPort());
            running = true;
            workers = Executors.newCachedThreadPool(task -> {
                Thread thread = new Thread(task, "mini-lis-mllp");
                thread.setDaemon(true);
                return thread;
            });
            Thread acceptor = new Thread(this::acceptLoop, "mini-lis-mllp-accept");
            acceptor.setDaemon(true);
            acceptor.start();
            log.info("hl7_mllp_started port={}", server.getLocalPort());
        } catch (Exception ex) {
            throw new IllegalStateException("Mini LIS HL7 listener did not start");
        }
    }

    public int port() {
        return server == null ? -1 : server.getLocalPort();
    }

    @PreDestroy
    public void stop() {
        running = false;
        if (server != null) {
            try {
                server.close();
            } catch (Exception ignored) {
                // The process is stopping.
            }
        }
        if (workers != null) {
            workers.shutdownNow();
        }
    }

    private void acceptLoop() {
        while (running) {
            try {
                Socket socket = server.accept();
                workers.execute(() -> handle(socket));
            } catch (Exception ex) {
                if (running) {
                    log.info("hl7_mllp_accept_failed");
                }
            }
        }
    }

    private void handle(Socket socket) {
        try (socket) {
            socket.setSoTimeout((int) properties.getReadTimeout().toMillis());
            String er7 = MllpExchange.read(socket.getInputStream());
            String ack = receiver.acknowledge(er7);
            MllpExchange.write(socket.getOutputStream(), ack);
        } catch (Exception ex) {
            log.info("hl7_mllp_session_failed");
        }
    }
}
