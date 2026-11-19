package lab.healthcare.minihis;

import com.fasterxml.jackson.databind.JsonNode;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Controller
@org.springframework.web.bind.annotation.ResponseBody
public class ShowcaseController {

    private final ShowcaseProbe probe;
    private final LabOrderStore orders;
    private final InpatientStore inpatient;
    private final ExchangeGateway exchange;
    private final String organizationId;
    private final String lisHealth;
    private final String fhirHealth;
    private final String aiHealth;
    private final String longitudinalHealth;
    private final String lisBench;

    public ShowcaseController(
            ShowcaseProbe probe,
            LabOrderStore orders,
            InpatientStore inpatient,
            ExchangeGateway exchange,
            @Value("${mini-his.organization-id}") String organizationId,
            @Value("${showcase.lis-health}") String lisHealth,
            @Value("${showcase.fhir-health}") String fhirHealth,
            @Value("${showcase.ai-health}") String aiHealth,
            @Value("${showcase.longitudinal-health:}") String longitudinalHealth,
            @Value("${showcase.lis-bench}") String lisBench) {
        this.probe = probe;
        this.orders = orders;
        this.inpatient = inpatient;
        this.exchange = exchange;
        this.organizationId = organizationId;
        this.lisHealth = lisHealth;
        this.fhirHealth = fhirHealth;
        this.aiHealth = aiHealth;
        this.longitudinalHealth = longitudinalHealth;
        this.lisBench = lisBench;
    }

    @GetMapping(path = "/showcase", produces = MediaType.TEXT_HTML_VALUE)
    public String index() {
        return ShowcaseView.index(ShowcaseCatalog.cards(probes()));
    }

    @GetMapping(path = "/showcase/{demoId}", produces = MediaType.TEXT_HTML_VALUE)
    public String demo(@PathVariable String demoId, HttpServletRequest request) {
        Map<String, Boolean> probes = probes();
        String availability = ShowcaseCatalog.availability(demoId, probes);
        if ("No disponible".equals(availability) && !known(demoId)) {
            return ShowcaseView.missing();
        }
        if (!known(demoId)) {
            return ShowcaseView.missing();
        }
        return ShowcaseView.demo(demoId, availability, steps(demoId), trace(demoId), csrf(request));
    }

    @PostMapping("/ward/showcase/episode")
    public ResponseEntity<Void> prepareEpisode(HttpServletRequest request) {
        if (!clinician(request) || !csrfOk(request)) {
            return redirect("/ward/login?aviso=no-autorizado");
        }
        try {
            String episodeId = inpatient.openEpisode("MHS-PAT-001", organizationId, principal(request).userId());
            return redirect("/ward/episodes/" + episodeId);
        } catch (InpatientRejection ex) {
            return redirect("/ward/episodes");
        }
    }

    private Map<String, Boolean> probes() {
        Map<String, Boolean> probes = new LinkedHashMap<>();
        probes.put("lis", probe.up(lisHealth));
        probes.put("fhir", probe.up(fhirHealth));
        probes.put("ai", probe.up(aiHealth));
        probes.put("longitudinal", probe.up(longitudinalHealth));
        return probes;
    }

    private List<ShowcaseCatalog.Step> steps(String demoId) {
        LabOrderView order = latestOrder();
        Map<String, Object> context = order == null ? Map.of() : orders.context(order.orderId());
        Map<String, Object> task = order == null ? null : orders.acknowledgement(order.orderId()).orElse(null);
        boolean correlated = order != null && present(order.correlationId());
        Reading reading = correlated ? reading(order) : Reading.none();
        EpisodeView episode = latestEpisode();
        String bench = probe.up(lisHealth) ? lisBench : "/showcase/demo-004";
        return switch (demoId) {
            case "demo-001" -> List.of(
                    step("Abrir el paciente sintético", "/ward/patients/MHS-PAT-001", false, "MHS-PAT-001"),
                    step("Consultar la ficha", "/ward/patients/MHS-PAT-001", false, "La ficha no ejecuta el resumen."),
                    step("Ejecutar el resumen", "/showcase/demo-001", false,
                            "El resumen usa un permiso nuevo del perfil de catálogo. Esta pantalla no lo lanza."),
                    step("Revisar la decisión", "/ward/audit", false, "La revisión de ese perfil no es esta sesión."));
            case "demo-002" -> List.of(
                    step("Abrir el perfil de Perú", "/showcase/demo-002", false, "org-pe-lab-demo queda en su propio despliegue."),
                    step("Abrir el perfil de España", "/showcase/demo-002", false, "org-es-lab-demo no comparte permisos con Perú."),
                    step("Aprobar con la identidad de ese país", "/showcase/demo-002", false,
                            "La sesión de Mini HIS no es el OIDC de ese perfil."));
            case "demo-003" -> List.of(
                    step("Crear la orden", "/ward/orders/new", order != null, order == null ? "Sin orden." : order.orderId()),
                    step("Enviar el intercambio", "/ward/orders", correlated, correlated ? order.correlationId() : "Sin correlación."),
                    step("Ver el resultado correlacionado", order == null ? "/ward/orders" : "/ward/orders/" + order.orderId(),
                            reading.present(), reading.present() ? reading.summary() : "El resultado todavía no está en el intercambio."),
                    step("Federación", "/showcase/demo-003", false, "La federación no se marca completa desde esta pantalla."));
            case "demo-004" -> List.of(
                    step("Crear orden", "/ward/orders/new", order != null, order == null ? "Sin orden." : order.orderId()),
                    step("Procesar muestra", bench, false, "El estado de la muestra se comprueba en Mini LIS."),
                    step("Publicar resultado", order == null ? "/ward/orders" : "/ward/orders/" + order.orderId(),
                            reading.present(), reading.present() ? reading.summary() : "Sin resultado publicado."),
                    step("Consultar alerta", order == null ? "/ward/orders" : "/ward/orders/" + order.orderId(),
                            reading.critical(), reading.critical() ? reading.summary() : "Sin alerta determinista."),
                    step("Ejecutar agente", order == null ? "/ward/orders" : "/ward/orders/" + order.orderId(),
                            present(context.get("proposal_id")), text(context.get("proposal_phase"))),
                    step("Revisar evidencias", order == null ? "/ward/orders" : "/ward/orders/" + order.orderId(),
                            present(context.get("protocol_ids")), text(context.get("protocol_ids"))),
                    step("Aprobar tarea", order == null ? "/ward/orders" : "/ward/orders/" + order.orderId(),
                            task != null, task == null ? "Sin tarea." : text(task.get("title"))),
                    step("Reconocer evento", order == null ? "/ward/orders" : "/ward/orders/" + order.orderId(),
                            task != null && "acknowledged".equals(text(task.get("status"))), text(task == null ? "" : task.get("status"))),
                    step("Consultar auditoría", "/ward/audit", task != null, "La auditoría muestra la tarea persistida."));
            case "demo-005" -> List.of(
                    step("Abrir episodio", episode.href(), episode.exists(), episode.id()),
                    step("Notas y resultados", episode.href(), episode.notes() && episode.results(), episode.note()),
                    step("Tareas pendientes", episode.href(), episode.wardTask(), episode.note()),
                    step("Borrador", episode.href(), episode.draft(), episode.note()),
                    step("Referencias", episode.href(), episode.draft(), "Las citas aparecen en la ficha, no en este portal."),
                    step("Aprobación", episode.href(), episode.accepted(), documentation(episode)),
                    step("Seguimiento", episode.href(), episode.followUp(), episode.note()));
            default -> List.of();
        };
    }

    private List<String> trace(String demoId) {
        List<String> lines = new ArrayList<>();
        if ("demo-002".equals(demoId)) {
            lines.add("Perú y España no se consultan desde esta base.");
            return lines;
        }
        for (LabOrderView order : orders.listAll()) {
            lines.add("Orden " + order.orderId() + " · " + order.localStatus()
                    + " · correlación " + (present(order.correlationId()) ? order.correlationId() : "ausente"));
            if (lines.size() == 3) {
                break;
            }
        }
        if (lines.isEmpty()) {
            lines.add("No hay órdenes nuevas en esta base.");
        }
        for (Map<String, Object> episode : inpatient.episodes()) {
            lines.add("Episodio " + episode.get("episode_id") + " · " + episode.get("status")
                    + " · documentación " + documentationLabel(String.valueOf(episode.get("documentation_status"))));
            if (lines.size() == 6) {
                break;
            }
        }
        return lines;
    }

    private LabOrderView latestOrder() {
        List<LabOrderView> all = orders.listAll();
        return all.isEmpty() ? null : all.get(0);
    }

    private Reading reading(LabOrderView order) {
        try {
            JsonNode report = exchange.report(order.orderId());
            CriticalHemoglobinRule.Reading reading = CriticalHemoglobinRule.read(report, order.testCode());
            if (!reading.critical() && (reading.value() == null || reading.value().isBlank())) {
                return Reading.none();
            }
            return new Reading(true, reading.critical(), reading.value() + " " + reading.unit());
        } catch (RuntimeException ex) {
            return Reading.none();
        }
    }

    private EpisodeView latestEpisode() {
        List<Map<String, Object>> episodes = inpatient.episodes();
        if (episodes.isEmpty()) {
            return EpisodeView.empty();
        }
        String id = String.valueOf(episodes.get(0).get("episode_id"));
        Map<String, Object> episode = inpatient.episode(id);
        List<?> notes = (List<?>) episode.get("notes");
        List<?> results = (List<?>) episode.get("results");
        List<?> tasks = (List<?>) episode.get("tasks");
        boolean ward = tasks.stream().anyMatch(item -> item instanceof Map<?, ?> map && "ward".equals(map.get("kind")));
        boolean follow = tasks.stream().anyMatch(item -> item instanceof Map<?, ?> map && "follow_up".equals(map.get("kind")));
        Object proposal = episode.get("proposal");
        boolean draft = proposal instanceof Map<?, ?> map && map.get("proposal_id") != null;
        return new EpisodeView("/ward/episodes/" + id, id, true, notes != null && !notes.isEmpty(),
                results != null && !results.isEmpty(), ward, draft,
                "accepted".equals(episode.get("documentation_status")), follow,
                String.valueOf(episode.get("documentation_status")));
    }

    private static ShowcaseCatalog.Step step(String label, String href, boolean done, String evidence) {
        return new ShowcaseCatalog.Step(label, href, done, evidence == null || evidence.isBlank() ? "Sin evidencia." : evidence);
    }

    private static boolean known(String demoId) {
        return demoId != null && demoId.matches("demo-00[1-5]");
    }

    private static boolean present(Object value) {
        return value != null && !String.valueOf(value).isBlank() && !"null".equals(String.valueOf(value));
    }

    private static String documentation(EpisodeView episode) {
        return episode.exists() ? documentationLabel(episode.documentation()) : "Sin episodio.";
    }

    private static String documentationLabel(String status) {
        return switch (status) {
            case "none" -> "sin documentación";
            case "proposed" -> "propuesta";
            case "accepted" -> "aceptada";
            default -> "sin documentación";
        };
    }

    private static String text(Object value) {
        return present(value) ? String.valueOf(value) : "Sin evidencia.";
    }

    private WardPrincipal principal(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        Object value = session == null ? null : session.getAttribute("wardPrincipal");
        return value instanceof WardPrincipal principal ? principal : null;
    }

    private boolean clinician(HttpServletRequest request) {
        WardPrincipal principal = principal(request);
        return principal != null && "clinician".equals(principal.role()) && organizationId.equals(principal.organizationId());
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

    private static ResponseEntity<Void> redirect(String path) {
        return ResponseEntity.status(303).location(URI.create(path)).build();
    }

    private record Reading(boolean present, boolean critical, String summary) {
        static Reading none() {
            return new Reading(false, false, "");
        }
    }

    private record EpisodeView(String href, String id, boolean exists, boolean notes, boolean results, boolean wardTask,
                               boolean draft, boolean accepted, boolean followUp, String documentation) {
        static EpisodeView empty() {
            return new EpisodeView("/ward/episodes", "Sin episodio.", false, false, false, false, false, false, false, "none");
        }

        String note() {
            return exists ? id : "Sin episodio.";
        }
    }
}
