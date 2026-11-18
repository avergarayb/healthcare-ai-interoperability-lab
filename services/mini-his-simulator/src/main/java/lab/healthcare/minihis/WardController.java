package lab.healthcare.minihis;

import com.fasterxml.jackson.databind.ObjectMapper;

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
            "aprobacion-invalida", "episodio-abierto");

    private final InpatientStore store;
    private final DischargeCoordinator coordinator;
    private final String organizationId;
    private final String password;
    private final ObjectMapper mapper = new ObjectMapper();

    public WardController(
            InpatientStore store,
            DischargeCoordinator coordinator,
            @Value("${mini-his.organization-id}") String organizationId,
            @Value("${mini-his.inpatient.ward-password:}") String password) {
        this.store = store;
        this.coordinator = coordinator;
        this.organizationId = organizationId;
        this.password = password == null ? "" : password;
    }

    @GetMapping(path = "/ward/login", produces = MediaType.TEXT_HTML_VALUE)
    public String loginPage() {
        return page("Ingreso", """
                <form method="post" action="/ward/login">
                  <label>Usuario <input name="username" autocomplete="username" required></label>
                  <label>Clave <input name="password" type="password" autocomplete="current-password" required></label>
                  <button type="submit">Entrar</button>
                </form>
                <p>Sesión de laboratorio para org-mini-his. No cierra episodios por sí sola.</p>
                """);
    }

    @PostMapping("/ward/login")
    public ResponseEntity<Void> login(
            @RequestParam String username, @RequestParam String password, HttpServletRequest request) {
        WardPrincipal principal = principalFor(username, password);
        if (principal == null) {
            return redirect("/ward/login");
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
        StringBuilder rows = new StringBuilder();
        for (Map<String, Object> patient : store.patients()) {
            String id = String.valueOf(patient.get("patient_id"));
            rows.append("<li><a href=\"/ward/patients/").append(esc(id)).append("\">")
                    .append(esc(id)).append(" ")
                    .append(esc(String.valueOf(patient.get("given_name")))).append(" ")
                    .append(esc(String.valueOf(patient.get("family_name"))))
                    .append("</a></li>");
        }
        return shell(request, "Pacientes", "<ul>" + rows + "</ul>");
    }

    @GetMapping(path = "/ward/patients/{patientId}", produces = MediaType.TEXT_HTML_VALUE)
    public String patient(@PathVariable String patientId, HttpServletRequest request) {
        try {
            Map<String, Object> patient = store.requirePatient(patientId);
            WardPrincipal principal = principal(request);
            String body = "<h1>" + esc(patientId) + " " + esc(String.valueOf(patient.get("given_name")))
                    + " " + esc(String.valueOf(patient.get("family_name"))) + "</h1>"
                    + clinicianForm(principal, "/ward/patients/" + patientId + "/episodes", csrf(request), """
                    <button type="submit">Abrir hospitalización</button>
                    """);
            return shell(request, "Paciente", body);
        } catch (InpatientRejection ex) {
            return shell(request, "Paciente", "<p>Paciente no disponible.</p>");
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
            return shell(request, "Episodio", renderEpisode(episode, request));
        } catch (InpatientRejection ex) {
            return shell(request, "Episodio", "<p>Episodio no disponible.</p>");
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

    private String renderEpisode(Map<String, Object> episode, HttpServletRequest request) {
        WardPrincipal principal = principal(request);
        String episodeId = String.valueOf(episode.get("episode_id"));
        String patientId = String.valueOf(episode.get("patient_id"));
        int version = ((Number) episode.get("version")).intValue();
        String csrf = csrf(request);
        StringBuilder html = new StringBuilder();
        html.append("<h1>Episodio ").append(esc(episodeId)).append("</h1>");
        html.append("<p>Paciente ").append(esc(patientId)).append(". Organización ")
                .append(esc(String.valueOf(episode.get("organization_id"))))
                .append(". Estado ").append(esc(String.valueOf(episode.get("status"))))
                .append(". Versión ").append(version)
                .append(". Documentación ").append(esc(String.valueOf(episode.get("documentation_status"))))
                .append(".</p>");
        html.append("<p>La aprobación de un borrador no cierra la hospitalización.</p>");
        html.append("<h2>Línea de tiempo</h2><ul>");
        for (Map<String, Object> event : rows(episode.get("timeline"))) {
            html.append("<li>").append(esc(String.valueOf(event.get("at")))).append(" ")
                    .append(esc(String.valueOf(event.get("label")))).append("</li>");
        }
        html.append("</ul><h2>Checklist</h2><ul>");
        Map<String, Object> checklist = rowsMap(episode.get("checklist"));
        for (String item : List.of("notes", "results", "allergies", "medications", "pending", "documentation")) {
            html.append("<li>").append(esc(item)).append(": ")
                    .append(Boolean.TRUE.equals(checklist.get(item)) ? "completo" : "pendiente")
                    .append("</li>");
        }
        html.append("</ul><p id=\"checklist-state\">")
                .append(Boolean.TRUE.equals(checklist.get("complete")) ? "Checklist completo" : "Checklist incompleto")
                .append("</p>");
        html.append("<h2>Notas</h2><ul>");
        for (Map<String, Object> note : rows(episode.get("notes"))) {
            html.append("<li>").append(esc(String.valueOf(note.get("note_id")))).append(": ")
                    .append(esc(String.valueOf(note.get("body")))).append("</li>");
        }
        html.append("</ul>");
        html.append(clinicianForm(principal, "/ward/episodes/" + episodeId + "/notes", csrf, """
                <input type="hidden" name="version" value="%d">
                <label>Nota <input name="body" required></label>
                <button type="submit">Registrar nota</button>
                """.formatted(version)));
        html.append("<h2>Alergias sintéticas</h2><ul>");
        for (Map<String, Object> allergy : rows(episode.get("allergies"))) {
            html.append("<li>").append(esc(String.valueOf(allergy.get("substance")))).append("</li>");
        }
        html.append("</ul>");
        html.append(clinicianForm(principal, "/ward/patients/" + patientId + "/allergies", csrf, """
                <input type="hidden" name="episodeId" value="%s">
                <label>Sustancia <input name="substance" required></label>
                <button type="submit">Registrar alergia</button>
                """.formatted(esc(episodeId))));
        html.append("<h2>Medicación documentada</h2><ul>");
        for (Map<String, Object> medication : rows(episode.get("medications"))) {
            html.append("<li>").append(esc(String.valueOf(medication.get("name")))).append(" ")
                    .append(esc(String.valueOf(medication.get("documented_status")))).append("</li>");
        }
        html.append("</ul>");
        html.append(clinicianForm(principal, "/ward/patients/" + patientId + "/medications", csrf, """
                <input type="hidden" name="episodeId" value="%s">
                <label>Nombre <input name="name" required></label>
                <label>Estado <select name="status"><option value="active">active</option><option value="stopped">stopped</option></select></label>
                <button type="submit">Registrar medicación</button>
                """.formatted(esc(episodeId))));
        html.append("<h2>Resultados</h2><ul>");
        for (Map<String, Object> result : rows(episode.get("results"))) {
            html.append("<li>").append(esc(String.valueOf(result.get("result_id")))).append(" ")
                    .append(esc(String.valueOf(result.get("display_name")))).append(" ")
                    .append(esc(String.valueOf(result.get("value_text")))).append(" ")
                    .append(esc(String.valueOf(result.get("unit")))).append("</li>");
        }
        html.append("</ul>");
        StringBuilder options = new StringBuilder();
        for (Map<String, Object> result : rows(episode.get("availableResults"))) {
            options.append("<option value=\"").append(esc(String.valueOf(result.get("result_id")))).append("\">")
                    .append(esc(String.valueOf(result.get("display_name")))).append("</option>");
        }
        html.append(clinicianForm(principal, "/ward/episodes/" + episodeId + "/results", csrf, """
                <input type="hidden" name="version" value="%d">
                <label>Resultado <select name="resultId">%s</select></label>
                <button type="submit">Asociar resultado</button>
                """.formatted(version, options)));
        html.append("<h2>Tareas</h2><ul>");
        for (Map<String, Object> task : rows(episode.get("tasks"))) {
            html.append("<li>").append(esc(String.valueOf(task.get("task_id")))).append(" ")
                    .append(esc(String.valueOf(task.get("kind")))).append(" ")
                    .append(esc(String.valueOf(task.get("status")))).append(" ")
                    .append(esc(String.valueOf(task.get("title"))));
            if ("ward".equals(task.get("kind")) && "open".equals(task.get("status"))) {
                html.append(clinicianForm(principal, "/ward/episodes/" + episodeId + "/tasks/" + task.get("task_id") + "/resolve", csrf,
                        "<input type=\"hidden\" name=\"version\" value=\"" + version + "\"><button type=\"submit\">Resolver</button>"));
            }
            html.append("</li>");
        }
        html.append("</ul>");
        html.append(clinicianForm(principal, "/ward/episodes/" + episodeId + "/tasks", csrf, """
                <input type="hidden" name="version" value="%d">
                <label>Tarea <input name="title" required></label>
                <button type="submit">Registrar pendiente</button>
                """.formatted(version)));
        html.append("<h2>Preparación de alta</h2>");
        html.append(clinicianForm(principal, "/ward/episodes/" + episodeId + "/prepare", csrf,
                "<button type=\"submit\">Solicitar preparación</button>"));
        Map<String, Object> proposal = rowsMap(episode.get("proposal"));
        if (!proposal.isEmpty()) {
            html.append("<pre id=\"proposal\">").append(esc(String.valueOf(proposal.get("body_json")))).append("</pre>");
            html.append(clinicianForm(principal, "/ward/episodes/" + episodeId + "/decision", csrf, """
                    <button name="decision" value="approved" type="submit">Aprobar borrador</button>
                    <button name="decision" value="rejected" type="submit">Rechazar</button>
                    <button name="decision" value="changes_requested" type="submit">Pedir corrección</button>
                    """));
            html.append(clinicianForm(principal, "/ward/episodes/" + episodeId + "/follow-ups", csrf, """
                    <input type="hidden" name="version" value="%d">
                    <button type="submit">Crear tareas de seguimiento autorizadas</button>
                    """.formatted(version)));
        }
        html.append("<h2>Auditoría del episodio</h2><ul id=\"audit\">");
        for (Map<String, Object> row : rows(episode.get("audit"))) {
            html.append("<li>").append(esc(String.valueOf(row.get("recorded_at")))).append(" ")
                    .append(esc(String.valueOf(row.get("actor_id")))).append(" ")
                    .append(esc(String.valueOf(row.get("action")))).append(" ")
                    .append(esc(String.valueOf(row.get("outcome")))).append("</li>");
        }
        html.append("</ul>");
        html.append(clinicianForm(principal, "/ward/episodes/" + episodeId + "/close", csrf, """
                <input type="hidden" name="version" value="%d">
                <button type="submit">Cerrar episodio</button>
                """.formatted(version)));
        return html.toString();
    }

    private String clinicianForm(WardPrincipal principal, String action, String csrf, String fields) {
        if (principal == null || !"clinician".equals(principal.role())) {
            return "";
        }
        return "<form method=\"post\" action=\"" + esc(action) + "\"><input type=\"hidden\" name=\"csrf\" value=\""
                + esc(csrf) + "\">" + fields + "</form>";
    }

    private String shell(HttpServletRequest request, String title, String body) {
        WardPrincipal principal = principal(request);
        String notice = noticeText(request);
        String who = principal == null ? "" : "<p>" + esc(principal.userId()) + " / " + esc(principal.role())
                + " / " + esc(principal.organizationId()) + "</p><form method=\"post\" action=\"/ward/logout\"><input type=\"hidden\" name=\"csrf\" value=\""
                + esc(csrf(request)) + "\"><button type=\"submit\">Salir</button></form>";
        return page(title, who + notice + body);
    }

    private static String page(String title, String body) {
        return """
                <!DOCTYPE html>
                <html lang="es"><head><meta charset="utf-8"><title>%s</title>
                <style>body{font-family:sans-serif;margin:2rem;max-width:52rem}form{margin:.5rem 0}label{display:block}</style>
                </head><body><nav><a href="/ward/patients">Pacientes</a></nav>%s</body></html>
                """.formatted(esc(title), body);
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

    private static String noticeText(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        if (session == null) {
            return "";
        }
        Object code = session.getAttribute("wardNotice");
        session.removeAttribute("wardNotice");
        if (!(code instanceof String text) || !NOTICES.contains(text)) {
            return "";
        }
        return "<p id=\"notice\">" + esc(text) + "</p>";
    }

    private static String noticeFor(InpatientRejection ex) {
        return switch (ex.code()) {
            case "version_conflict" -> "version-conflicto";
            case "coordinator_unavailable", "coordinator_unconfigured", "coordinator_rejected" -> "coordinador-no-disponible";
            case "invalid_input" -> "entrada-invalida";
            default -> "entrada-invalida";
        };
    }

    private static ResponseEntity<Void> redirect(String path) {
        return ResponseEntity.status(303).location(URI.create(path)).build();
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> rows(Object value) {
        return value instanceof List<?> list ? (List<Map<String, Object>>) list : List.of();
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> rowsMap(Object value) {
        return value instanceof Map<?, ?> map ? (Map<String, Object>) map : Map.of();
    }

    private static String esc(String value) {
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;");
    }
}
