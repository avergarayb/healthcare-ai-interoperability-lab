package lab.healthcare.minihis;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

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
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

@Controller
@org.springframework.web.bind.annotation.ResponseBody
public class WardController {

    private static final Set<String> NOTICES = Set.of(
            "nota-registrada", "alergia-registrada", "medicacion-registrada", "resultado-asociado",
            "tarea-abierta", "tarea-resuelta", "preparacion-lista", "preparacion-pendiente",
            "decision-registrada", "seguimiento-creado", "episodio-cerrado", "version-conflicto",
            "no-autorizado", "coordinador-no-disponible", "entrada-invalida", "ya-registrado",
            "aprobacion-invalida", "episodio-abierto", "orden-registrada", "orden-enviada",
            "orden-no-enviada", "agente-preparado", "agente-no-disponible", "decision-aprobada",
            "rechazada", "reconocido", "escalado");

    private final InpatientStore store;
    private final DischargeCoordinator coordinator;
    private final LabOrderStore orders;
    private final MiniHisStore patients;
    private final ExchangeGateway exchange;
    private final CriticalLabClient criticalLab;
    private final String organizationId;
    private final String password;
    private final ObjectMapper mapper = new ObjectMapper();

    public WardController(
            InpatientStore store,
            DischargeCoordinator coordinator,
            LabOrderStore orders,
            MiniHisStore patients,
            ExchangeGateway exchange,
            CriticalLabClient criticalLab,
            @Value("${mini-his.organization-id}") String organizationId,
            @Value("${mini-his.inpatient.ward-password:}") String password) {
        this.store = store;
        this.coordinator = coordinator;
        this.orders = orders;
        this.patients = patients;
        this.exchange = exchange;
        this.criticalLab = criticalLab;
        this.organizationId = organizationId;
        this.password = password == null ? "" : password;
    }

    @GetMapping(path = "/ward/login", produces = MediaType.TEXT_HTML_VALUE)
    public String loginPage(@RequestParam(name = "aviso", required = false) String notice) {
        return WardView.login("credenciales".equals(notice) || "sesion".equals(notice) ? notice : "");
    }

    @PostMapping("/ward/login")
    public ResponseEntity<Void> login(
            @RequestParam String username, @RequestParam String password, HttpServletRequest request) {
        WardPrincipal principal = principalFor(username, password);
        if (principal == null) {
            return redirect("/ward/login?aviso=credenciales");
        }
        HttpSession session = request.getSession(true);
        session.invalidate();
        session = request.getSession(true);
        session.setAttribute("wardPrincipal", principal);
        session.setAttribute("csrf", UUID.randomUUID().toString());
        return redirect("/ward/patients");
    }

    @PostMapping("/ward/logout")
    public ResponseEntity<Void> logout(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        if (session != null) {
            session.invalidate();
        }
        return redirect("/ward/login");
    }

    @GetMapping(path = "/ward/patients", produces = MediaType.TEXT_HTML_VALUE)
    public String patients(HttpServletRequest request) {
        store.ensure();
        return WardView.patients(principal(request), csrf(request), takeNotice(request), store.patients());
    }

    @GetMapping(path = "/ward/episodes", produces = MediaType.TEXT_HTML_VALUE)
    public String episodes(HttpServletRequest request) {
        return WardView.episodes(principal(request), csrf(request), takeNotice(request), store.episodes());
    }

    @GetMapping(path = "/ward/tasks", produces = MediaType.TEXT_HTML_VALUE)
    public String tasks(HttpServletRequest request) {
        return WardView.tasks(principal(request), csrf(request), takeNotice(request), store.allTasks());
    }

    @GetMapping(path = "/ward/audit", produces = MediaType.TEXT_HTML_VALUE)
    public String audit(HttpServletRequest request) {
        return WardView.auditIndex(principal(request), csrf(request), takeNotice(request), store.recentAudit());
    }

    @GetMapping(path = "/ward/patients/{patientId}", produces = MediaType.TEXT_HTML_VALUE)
    public String patient(@PathVariable String patientId, HttpServletRequest request) {
        try {
            Map<String, Object> patient = store.requirePatient(patientId);
            WardPrincipal principal = principal(request);
            return WardView.patient(principal, csrf(request), takeNotice(request), patient);
        } catch (InpatientRejection ex) {
            return WardView.missing(principal(request), csrf(request), takeNotice(request), "Paciente");
        }
    }

    @PostMapping("/ward/patients/{patientId}/episodes")
    public ResponseEntity<Void> open(@PathVariable String patientId, HttpServletRequest request) {
        if (!clinician(request) || !csrfOk(request)) {
            return redirect("/ward/patients/" + patientId);
        }
        try {
            String episodeId = store.openEpisode(patientId, organizationId, principal(request).userId());
            notice(request, "episodio-abierto");
            return redirect("/ward/episodes/" + episodeId);
        } catch (InpatientRejection ex) {
            notice(request, "entrada-invalida");
            return redirect("/ward/patients/" + patientId);
        }
    }

    @GetMapping(path = "/ward/episodes/{episodeId}", produces = MediaType.TEXT_HTML_VALUE)
    public String episode(@PathVariable String episodeId, HttpServletRequest request) {
        try {
            Map<String, Object> episode = store.episode(episodeId);
            return WardView.episode(principal(request), csrf(request), takeNotice(request), episode, store.requirePatient(String.valueOf(episode.get("patient_id"))));
        } catch (InpatientRejection ex) {
            return WardView.missing(principal(request), csrf(request), takeNotice(request), "Episodio");
        }
    }

    @PostMapping("/ward/episodes/{episodeId}/notes")
    public ResponseEntity<Void> note(
            @PathVariable String episodeId, @RequestParam int version, @RequestParam String body, HttpServletRequest request) {
        return mutate(request, episodeId, () -> store.addNote(episodeId, version, principal(request).userId(), body), "nota-registrada");
    }

    @PostMapping("/ward/patients/{patientId}/allergies")
    public ResponseEntity<Void> allergy(
            @PathVariable String patientId, @RequestParam String episodeId, @RequestParam String substance, HttpServletRequest request) {
        if (!clinician(request) || !csrfOk(request)) {
            return redirect("/ward/episodes/" + episodeId);
        }
        try {
            store.addAllergy(patientId, principal(request).userId(), substance);
            notice(request, "alergia-registrada");
        } catch (InpatientRejection ex) {
            notice(request, noticeFor(ex));
        }
        return redirect("/ward/episodes/" + episodeId);
    }

    @PostMapping("/ward/patients/{patientId}/medications")
    public ResponseEntity<Void> medication(
            @PathVariable String patientId, @RequestParam String episodeId, @RequestParam String name,
            @RequestParam String status, HttpServletRequest request) {
        if (!clinician(request) || !csrfOk(request)) {
            return redirect("/ward/episodes/" + episodeId);
        }
        try {
            store.addMedication(patientId, principal(request).userId(), name, status);
            notice(request, "medicacion-registrada");
        } catch (InpatientRejection ex) {
            notice(request, noticeFor(ex));
        }
        return redirect("/ward/episodes/" + episodeId);
    }

    @PostMapping("/ward/episodes/{episodeId}/results")
    public ResponseEntity<Void> result(
            @PathVariable String episodeId, @RequestParam int version, @RequestParam String resultId, HttpServletRequest request) {
        return mutate(request, episodeId, () -> store.linkResult(episodeId, version, principal(request).userId(), resultId), "resultado-asociado");
    }

    @PostMapping("/ward/episodes/{episodeId}/tasks")
    public ResponseEntity<Void> task(
            @PathVariable String episodeId, @RequestParam int version, @RequestParam String title, HttpServletRequest request) {
        return mutate(request, episodeId, () -> store.addTask(episodeId, version, principal(request).userId(), title), "tarea-abierta");
    }

    @PostMapping("/ward/episodes/{episodeId}/tasks/{taskId}/resolve")
    public ResponseEntity<Void> resolve(
            @PathVariable String episodeId, @PathVariable String taskId, @RequestParam int version, HttpServletRequest request) {
        return mutate(request, episodeId, () -> store.resolveTask(episodeId, taskId, version, principal(request).userId()), "tarea-resuelta");
    }

    @PostMapping("/ward/episodes/{episodeId}/prepare")
    public ResponseEntity<Void> prepare(@PathVariable String episodeId, HttpServletRequest request) {
        if (!clinician(request) || !csrfOk(request)) {
            return redirect("/ward/episodes/" + episodeId);
        }
        try {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("authorizationId", "dis" + UUID.randomUUID().toString().replace("-", ""));
            body.put("episodeId", episodeId);
            body.put("organizationId", organizationId);
            body.put("principalId", principal(request).userId());
            body.put("role", "clinician");
            Map<String, Object> prepared = coordinator.prepare(body);
            prepared.put("bodyJson", mapper.writeValueAsString(prepared));
            if (prepared.get("proposalId") != null) {
                store.rememberProposal(episodeId, prepared);
            }
            notice(request, "PENDING_REVIEW".equals(prepared.get("phase")) ? "preparacion-lista" : "preparacion-pendiente");
        } catch (InpatientRejection ex) {
            notice(request, noticeFor(ex));
        } catch (Exception ex) {
            notice(request, "coordinador-no-disponible");
        }
        return redirect("/ward/episodes/" + episodeId);
    }

    @PostMapping("/ward/episodes/{episodeId}/decision")
    public ResponseEntity<Void> decision(
            @PathVariable String episodeId, @RequestParam String decision, HttpServletRequest request) {
        if (!clinician(request) || !csrfOk(request) || !Set.of("approved", "rejected", "changes_requested").contains(decision)) {
            notice(request, "no-autorizado");
            return redirect("/ward/episodes/" + episodeId);
        }
        Map<String, Object> stored = store.storedProposal(episodeId);
        if (stored.isEmpty()) {
            notice(request, "preparacion-pendiente");
            return redirect("/ward/episodes/" + episodeId);
        }
        try {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("proposalId", stored.get("proposal_id"));
            body.put("proposalHash", stored.get("proposal_hash"));
            body.put("episodeId", episodeId);
            body.put("episodeVersion", stored.get("episode_version"));
            body.put("decision", decision);
            body.put("actorId", principal(request).userId());
            body.put("role", "clinician");
            body.put("organizationId", organizationId);
            body.put("idempotencyKey", "dec" + UUID.randomUUID().toString().replace("-", ""));
            Map<String, Object> result = coordinator.decide(body);
            if ("approved".equals(result.get("outcome")) && Boolean.FALSE.equals(result.get("episodeClosed"))) {
                store.markDocumentationAccepted(episodeId, principal(request).userId(), String.valueOf(stored.get("proposal_id")));
            }
            notice(request, "decision-registrada");
        } catch (InpatientRejection ex) {
            notice(request, noticeFor(ex));
        }
        return redirect("/ward/episodes/" + episodeId);
    }

    @PostMapping("/ward/episodes/{episodeId}/follow-ups")
    public ResponseEntity<Void> followUps(@PathVariable String episodeId, @RequestParam int version, HttpServletRequest request) {
        if (!clinician(request) || !csrfOk(request)) {
            return redirect("/ward/episodes/" + episodeId);
        }
        Map<String, Object> stored = store.storedProposal(episodeId);
        if (stored.isEmpty()) {
            notice(request, "preparacion-pendiente");
            return redirect("/ward/episodes/" + episodeId);
        }
        try {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("proposalId", stored.get("proposal_id"));
            body.put("proposalHash", stored.get("proposal_hash"));
            body.put("episodeId", episodeId);
            body.put("actorId", principal(request).userId());
            body.put("role", "clinician");
            body.put("organizationId", organizationId);
            Map<String, Object> allowed = coordinator.authorize(body);
            if (!"authorized".equals(allowed.get("outcome")) && !"already_created".equals(allowed.get("outcome"))) {
                notice(request, "aprobacion-invalida");
                return redirect("/ward/episodes/" + episodeId);
            }
            List<String> titles = new ArrayList<>();
            Object tasks = allowed.get("tasks");
            if (tasks instanceof List<?> list) {
                for (Object item : list) {
                    if (item instanceof Map<?, ?> map && map.get("title") instanceof String title) {
                        titles.add(title);
                    }
                }
            }
            store.createFollowUps(episodeId, version, principal(request).userId(), String.valueOf(stored.get("proposal_id")), titles);
            notice(request, "seguimiento-creado");
        } catch (InpatientRejection ex) {
            notice(request, noticeFor(ex));
        }
        return redirect("/ward/episodes/" + episodeId);
    }

    @PostMapping("/ward/episodes/{episodeId}/close")
    public ResponseEntity<Void> close(@PathVariable String episodeId, @RequestParam int version, HttpServletRequest request) {
        return mutate(request, episodeId, () -> store.close(episodeId, version, principal(request).userId()), "episodio-cerrado");
    }

    @GetMapping(path = "/ward/orders", produces = MediaType.TEXT_HTML_VALUE)
    public String orders(HttpServletRequest request) {
        return WardView.orders(principal(request), csrf(request), takeNotice(request), orders.listAll());
    }

    @GetMapping(path = "/ward/orders/new", produces = MediaType.TEXT_HTML_VALUE)
    public String newOrder(HttpServletRequest request) {
        if (!clinician(request)) {
            notice(request, "no-autorizado");
            return orders(request);
        }
        return WardView.orderForm(principal(request), csrf(request), takeNotice(request), store.patients(), store.episodes());
    }

    @PostMapping("/ward/orders")
    public ResponseEntity<Void> createOrder(
            @RequestParam String patientId,
            @RequestParam(required = false) String episodeId,
            @RequestParam String testCode,
            @RequestParam String indication,
            @RequestParam String requestedOn,
            HttpServletRequest request) {
        if (!clinician(request) || !csrfOk(request)) {
            notice(request, "no-autorizado");
            return redirect("/ward/orders");
        }
        if (!"718-7".equals(testCode) || patients.findPatient(patientId).isEmpty()
                || indication == null || indication.isBlank() || indication.length() > 200 || indication.indexOf('<') >= 0) {
            notice(request, "entrada-invalida");
            return redirect("/ward/orders/new");
        }
        LocalDate day;
        try {
            day = LocalDate.parse(requestedOn);
        } catch (RuntimeException ex) {
            notice(request, "entrada-invalida");
            return redirect("/ward/orders/new");
        }
        if (episodeId != null && !episodeId.isBlank() && store.episodes().stream()
                .noneMatch(row -> episodeId.equals(row.get("episode_id")) && patientId.equals(row.get("patient_id")))) {
            notice(request, "entrada-invalida");
            return redirect("/ward/orders/new");
        }
        LabOrderView created = orders.insert(
                patientId, "mini-lis", testCode, "Hemoglobina", day.atTime(12, 0).atOffset(ZoneOffset.UTC).toString());
        orders.rememberContext(created.orderId(), episodeId, indication.trim());
        notice(request, "orden-registrada");
        return submitOrder(created.orderId(), request);
    }

    @PostMapping("/ward/orders/{orderId}/submission")
    public ResponseEntity<Void> submitOrder(@PathVariable String orderId, HttpServletRequest request) {
        if (!clinician(request) || !csrfOk(request)) {
            notice(request, "no-autorizado");
            return redirect("/ward/orders/" + orderId);
        }
        LabOrderView order = orders.find(orderId).orElse(null);
        PatientView patient = order == null ? null : patients.findPatient(order.patientId()).orElse(null);
        if (order == null || patient == null) {
            notice(request, "entrada-invalida");
            return redirect("/ward/orders");
        }
        if ("submitted".equals(order.localStatus())) {
            notice(request, "ya-registrado");
            return redirect("/ward/orders/" + orderId);
        }
        ObjectNode body = mapper.createObjectNode();
        body.put("sourceOrganizationId", organizationId);
        body.put("destinationSystemKey", order.destinationSystemKey());
        body.put("externalRequestId", order.orderId());
        body.put("testCode", order.testCode());
        body.put("testDescription", order.testDescription());
        body.put("requestedAt", order.requestedAt());
        ObjectNode identity = body.putObject("patient");
        identity.put("identifierSystem", SyntheticSeed.PROPRIETARY_PATIENT_SYSTEM);
        identity.put("identifierValue", patient.patientId());
        identity.put("familyName", patient.familyName());
        identity.put("givenName", patient.givenName());
        identity.put("birthDate", patient.birthDate());
        identity.put("administrativeSex", patient.administrativeSex());
        try {
            JsonNode accepted = exchange.submit(body);
            orders.markSubmitted(
                    order.orderId(),
                    accepted.path("correlationId").asText(),
                    accepted.path("destination").path("orderId").asText(),
                    accepted.path("destination").path("organizationId").asText());
            notice(request, "orden-enviada");
        } catch (ExchangeGateway.ExchangeGatewayException ex) {
            orders.markFailed(order.orderId());
            notice(request, "orden-no-enviada");
        }
        return redirect("/ward/orders/" + orderId);
    }

    @GetMapping(path = "/ward/orders/{orderId}", produces = MediaType.TEXT_HTML_VALUE)
    public String order(@PathVariable String orderId, HttpServletRequest request) {
        LabOrderView order = orders.find(orderId).orElse(null);
        if (order == null) {
            notice(request, "entrada-invalida");
            return orders(request);
        }
        CriticalHemoglobinRule.Reading reading = new CriticalHemoglobinRule.Reading("", "", false);
        String reportError = "";
        if (order.correlationId() != null && !order.correlationId().isBlank()) {
            try {
                reading = CriticalHemoglobinRule.read(exchange.report(order.orderId()), order.testCode());
            } catch (ExchangeGateway.ExchangeGatewayException ex) {
                reportError = "El resultado no pudo leerse.";
            }
        }
        return WardView.orderDetail(
                principal(request), csrf(request), takeNotice(request), order, orders.context(orderId),
                reading, reportError, orders.acknowledgement(orderId).orElse(null));
    }

    @PostMapping("/ward/orders/{orderId}/preparation")
    public ResponseEntity<Void> prepareCritical(@PathVariable String orderId, HttpServletRequest request) {
        if (!clinician(request) || !csrfOk(request)) {
            notice(request, "no-autorizado");
            return redirect("/ward/orders/" + orderId);
        }
        LabOrderView order = orders.find(orderId).orElse(null);
        if (order == null || order.destinationOrderId() == null || order.destinationOrderId().isBlank()) {
            notice(request, "entrada-invalida");
            return redirect("/ward/orders/" + orderId);
        }
        Map<String, Object> context = orders.context(orderId);
        Object episode = context.get("episode_id");
        try {
            Map<String, Object> prepared = criticalLab.prepare(Map.of(
                    "orderId", order.destinationOrderId(),
                    "organizationId", organizationId,
                    "episodeId", episode == null ? "" : String.valueOf(episode),
                    "actorId", principal(request).userId()));
            orders.rememberProposal(
                    orderId,
                    String.valueOf(prepared.get("proposalId")),
                    String.valueOf(prepared.get("proposalHash")),
                    String.valueOf(prepared.getOrDefault("proposal", "")),
                    String.valueOf(prepared.getOrDefault("phase", "")),
                    String.valueOf(prepared.getOrDefault("protocolIds", "")));
            notice(request, "PENDING_REVIEW".equals(prepared.get("phase")) ? "agente-preparado" : "agente-no-disponible");
        } catch (InpatientRejection ex) {
            notice(request, noticeFor(ex));
        }
        return redirect("/ward/orders/" + orderId);
    }

    @PostMapping("/ward/orders/{orderId}/decision")
    public ResponseEntity<Void> decideCritical(
            @PathVariable String orderId, @RequestParam String decision, HttpServletRequest request) {
        if (!clinician(request) || !csrfOk(request) || (!"approved".equals(decision) && !"rejected".equals(decision))) {
            notice(request, "no-autorizado");
            return redirect("/ward/orders/" + orderId);
        }
        Map<String, Object> context = orders.context(orderId);
        if (context.get("proposal_id") == null) {
            notice(request, "aprobacion-invalida");
            return redirect("/ward/orders/" + orderId);
        }
        if (orders.acknowledgement(orderId).isPresent()) {
            notice(request, "ya-registrado");
            return redirect("/ward/orders/" + orderId);
        }
        try {
            Map<String, Object> recorded = criticalLab.decide(Map.of(
                    "proposalId", context.get("proposal_id"),
                    "proposalHash", context.get("proposal_hash"),
                    "decision", decision,
                    "actorId", principal(request).userId(),
                    "organizationId", organizationId,
                    "idempotencyKey", UUID.randomUUID().toString()));
            if (!"recorded".equals(recorded.get("outcome"))) {
                notice(request, "aprobacion-invalida");
                return redirect("/ward/orders/" + orderId);
            }
            orders.rememberProposal(
                    orderId,
                    String.valueOf(context.get("proposal_id")),
                    String.valueOf(context.get("proposal_hash")),
                    String.valueOf(context.get("proposal_summary")),
                    "approved".equals(decision) ? "APPROVED" : "REJECTED",
                    String.valueOf(context.get("protocol_ids")));
            if ("rejected".equals(decision)) {
                notice(request, "rechazada");
                return redirect("/ward/orders/" + orderId);
            }
            Map<String, Object> applied = criticalLab.apply(Map.of(
                    "proposalId", context.get("proposal_id"),
                    "proposalHash", context.get("proposal_hash"),
                    "organizationId", organizationId,
                    "actorId", principal(request).userId()));
            String outcome = String.valueOf(applied.get("outcome"));
            if ("created".equals(outcome) || "already_created".equals(outcome)) {
                if (orders.acknowledgement(orderId).isEmpty()) {
                    orders.insertAcknowledgement(
                            orderId,
                            String.valueOf(context.get("proposal_id")),
                            String.valueOf(context.get("proposal_hash")),
                            "Reconocer hemoglobina crítica",
                            principal(request).userId(),
                            OffsetDateTime.now(ZoneOffset.UTC).toString());
                }
                notice(request, "decision-aprobada");
            } else {
                notice(request, "rechazada");
            }
        } catch (InpatientRejection ex) {
            notice(request, noticeFor(ex));
        }
        return redirect("/ward/orders/" + orderId);
    }

    @PostMapping("/ward/orders/{orderId}/acknowledgement")
    public ResponseEntity<Void> acknowledge(@PathVariable String orderId, HttpServletRequest request) {
        return finishTask(request, orderId, true);
    }

    @PostMapping("/ward/orders/{orderId}/escalation")
    public ResponseEntity<Void> escalate(@PathVariable String orderId, HttpServletRequest request) {
        return finishTask(request, orderId, false);
    }

    private ResponseEntity<Void> finishTask(HttpServletRequest request, String orderId, boolean acknowledge) {
        if (!clinician(request) || !csrfOk(request)) {
            notice(request, "no-autorizado");
            return redirect("/ward/orders/" + orderId);
        }
        Map<String, Object> row = orders.acknowledgement(orderId).orElse(null);
        if (row == null || !"open".equals(row.get("status"))) {
            notice(request, "ya-registrado");
            return redirect("/ward/orders/" + orderId);
        }
        String at = OffsetDateTime.now(ZoneOffset.UTC).toString();
        if (acknowledge) {
            orders.markAcknowledged(orderId, at);
            notice(request, "reconocido");
        } else {
            orders.markEscalated(orderId, at);
            notice(request, "escalado");
        }
        return redirect("/ward/orders/" + orderId);
    }

    private ResponseEntity<Void> mutate(HttpServletRequest request, String episodeId, Runnable action, String success) {
        if (!clinician(request) || !csrfOk(request)) {
            notice(request, "no-autorizado");
            return redirect("/ward/episodes/" + episodeId);
        }
        try {
            action.run();
            notice(request, success);
        } catch (InpatientRejection ex) {
            notice(request, noticeFor(ex));
        }
        return redirect("/ward/episodes/" + episodeId);
    }

    private static String takeNotice(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        if (session == null) return "";
        Object code = session.getAttribute("wardNotice");
        session.removeAttribute("wardNotice");
        return code instanceof String text && NOTICES.contains(text) ? text : "";
    }


    private WardPrincipal principalFor(String username, String presented) {
        if (password.isBlank() || presented == null) {
            return null;
        }
        if (!MessageDigest.isEqual(password.getBytes(StandardCharsets.UTF_8), presented.getBytes(StandardCharsets.UTF_8))) {
            return null;
        }
        if ("clinica".equals(username)) {
            return new WardPrincipal("clinica", "clinician", organizationId);
        }
        if ("auditor".equals(username)) {
            return new WardPrincipal("auditor", "auditor", organizationId);
        }
        return null;
    }

    private static WardPrincipal principal(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        Object value = session == null ? null : session.getAttribute("wardPrincipal");
        return value instanceof WardPrincipal principal ? principal : null;
    }

    private static boolean clinician(HttpServletRequest request) {
        WardPrincipal principal = principal(request);
        return principal != null && "clinician".equals(principal.role()) && "org-mini-his".equals(principal.organizationId());
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
            session.setAttribute("wardNotice", code);
        }
    }


    private static String noticeFor(InpatientRejection ex) {
        return switch (ex.code()) {
            case "version_conflict" -> "version-conflicto";
            case "coordinator_unavailable", "coordinator_unconfigured", "coordinator_rejected" -> "coordinador-no-disponible";
            case "critical_agent_unavailable", "critical_agent_unconfigured", "critical_agent_rejected" -> "agente-no-disponible";
            case "invalid_input" -> "entrada-invalida";
            default -> "entrada-invalida";
        };
    }

    private static ResponseEntity<Void> redirect(String path) {
        return ResponseEntity.status(303).location(URI.create(path)).build();
    }

}
