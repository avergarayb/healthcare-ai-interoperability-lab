package lab.healthcare.minilis;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

@Controller
@org.springframework.web.bind.annotation.ResponseBody
public class BenchController {

    private static final Set<String> NOTICES = Set.of(
            "muestra-registrada", "muestra-recibida", "procesamiento", "borrador", "validado",
            "publicado", "corregido", "transicion", "no-autorizado", "entrada", "sesion", "credenciales");

    private final LaboratoryRecordService records;
    private final BenchWorkflow workflow;
    private final String password;

    public BenchController(
            LaboratoryRecordService records,
            BenchWorkflow workflow,
            @Value("${mini-lis.bench-password:}") String password) {
        this.records = records;
        this.workflow = workflow;
        this.password = password == null ? "" : password;
    }

    @GetMapping(path = "/bench/login", produces = MediaType.TEXT_HTML_VALUE)
    public String loginForm(@RequestParam(name = "aviso", required = false) String notice) {
        return BenchView.login(notice == null ? "" : notice);
    }

    @PostMapping("/bench/login")
    public ResponseEntity<Void> login(@RequestParam String username, @RequestParam String password, HttpServletRequest request) {
        BenchPrincipal principal = principalFor(username, password);
        if (principal == null) {
            return redirect("/bench/login?aviso=credenciales");
        }
        HttpSession session = request.getSession(true);
        session.setAttribute("benchPrincipal", principal);
        session.setAttribute("csrf", UUID.randomUUID().toString());
        return redirect("/bench/orders");
    }

    @PostMapping("/bench/logout")
    public ResponseEntity<Void> logout(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        if (session != null) {
            session.invalidate();
        }
        return redirect("/bench/login");
    }

    @GetMapping(path = "/bench/orders", produces = MediaType.TEXT_HTML_VALUE)
    public String orders(@RequestParam(name = "vista", required = false) String view, HttpServletRequest request) {
        BenchPrincipal principal = principal(request);
        List<LabOrder> orders = records.listOrders(50);
        Map<String, String> states = new LinkedHashMap<>();
        Map<String, String> names = new LinkedHashMap<>();
        for (LabOrder order : orders) {
            states.put(order.orderId(), workflow.stateOf(order.orderId()));
            ExternalPatient patient = records.patient(order.patientId());
            names.put(order.patientId(), patient.givenName() + " " + patient.familyName());
        }
        String active = switch (view == null ? "" : view) {
            case "muestras" -> "samples";
            case "procesamiento" -> "processing";
            case "resultados" -> "results";
            case "validacion" -> "validation";
            case "alertas" -> "alerts";
            default -> "orders";
        };
        return BenchView.orders(principal, csrf(request), takeNotice(request), active, orders, states, names);
    }

    @GetMapping(path = "/bench/orders/{orderId}", produces = MediaType.TEXT_HTML_VALUE)
    public String order(@PathVariable String orderId, HttpServletRequest request) {
        LabOrder order = records.order(orderId);
        return BenchView.order(
                principal(request),
                csrf(request),
                takeNotice(request),
                order,
                records.patient(order.patientId()),
                workflow.find(orderId).orElse(null),
                workflow.criticalEvent(orderId).orElse(null),
                records.resultsForOrder(orderId).size());
    }

    @PostMapping("/bench/orders/{orderId}")
    public ResponseEntity<Void> advance(
            @PathVariable String orderId,
            @RequestParam String action,
            @RequestParam(required = false) String value,
            @RequestParam(required = false) String unit,
            @RequestParam(required = false) String note,
            HttpServletRequest request) {
        if (!csrfOk(request)) {
            notice(request, "no-autorizado");
            return redirect("/bench/orders/" + orderId);
        }
        BenchPrincipal principal = principal(request);
        try {
            workflow.advance(orderId, action, value, unit, note, principal.validator());
            notice(request, switch (action) {
                case "register" -> "muestra-registrada";
                case "receive" -> "muestra-recibida";
                case "process" -> "procesamiento";
                case "draft" -> "borrador";
                case "validate" -> "validado";
                case "publish" -> "publicado";
                case "correct" -> "corregido";
                default -> "transicion";
            });
        } catch (MiniLisException ex) {
            notice(request, switch (ex.code()) {
                case "unauthorized" -> "no-autorizado";
                case "invalid_request" -> "entrada";
                default -> "transicion";
            });
        }
        return redirect("/bench/orders/" + orderId);
    }

    @GetMapping(path = "/bench/audit", produces = MediaType.TEXT_HTML_VALUE)
    public String audit(HttpServletRequest request) {
        return BenchView.audit(principal(request), csrf(request), takeNotice(request), workflow.criticalEvents());
    }

    private BenchPrincipal principalFor(String username, String presented) {
        if (password.isBlank() || presented == null) {
            return null;
        }
        if (!MessageDigest.isEqual(password.getBytes(StandardCharsets.UTF_8), presented.getBytes(StandardCharsets.UTF_8))) {
            return null;
        }
        if ("tecnico".equals(username)) {
            return new BenchPrincipal("tecnico", false);
        }
        if ("validador".equals(username)) {
            return new BenchPrincipal("validador", true);
        }
        return null;
    }

    private static BenchPrincipal principal(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        Object value = session == null ? null : session.getAttribute("benchPrincipal");
        return value instanceof BenchPrincipal principal ? principal : null;
    }

    private static boolean csrfOk(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        Object expected = session == null ? null : session.getAttribute("csrf");
        String presented = request.getParameter("csrf");
        return expected instanceof String token && presented != null
                && MessageDigest.isEqual(token.getBytes(StandardCharsets.UTF_8), presented.getBytes(StandardCharsets.UTF_8));
    }

    private static String csrf(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        Object value = session == null ? null : session.getAttribute("csrf");
        return value instanceof String token ? token : "";
    }

    private static void notice(HttpServletRequest request, String code) {
        HttpSession session = request.getSession(false);
        if (session != null && NOTICES.contains(code)) {
            session.setAttribute("benchNotice", code);
        }
    }

    private static String takeNotice(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        if (session == null) {
            return "";
        }
        Object code = session.getAttribute("benchNotice");
        session.removeAttribute("benchNotice");
        return code instanceof String text && NOTICES.contains(text) ? text : "";
    }

    private static ResponseEntity<Void> redirect(String path) {
        return ResponseEntity.status(303).location(URI.create(path)).build();
    }

    public record BenchPrincipal(String userId, boolean validator) {
    }
}
