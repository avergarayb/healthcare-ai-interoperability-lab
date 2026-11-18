package lab.healthcare.minihis;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Locale;
import java.util.Map;

final class WardView {

    private static final DateTimeFormatter WHEN = DateTimeFormatter.ofPattern("d MMM yyyy, HH:mm", Locale.forLanguageTag("es"))
            .withZone(ZoneId.of("America/Lima"));
    private static final ObjectMapper JSON = new ObjectMapper();

    private WardView() {
    }

    static String login(String notice) {
        return """
                <!DOCTYPE html>
                <html lang="es"><head>%s<title>Ingreso</title></head>
                <body><a class="skip" href="#contenido">Saltar al contenido</a>
                <main class="login-wrap" id="contenido"><section class="card login-card">
                  <p class="kicker">Healthcare Lab</p>
                  <h1>Mini HIS</h1>
                  <p class="muted">Sesión de laboratorio de la organización. No es un acceso OIDC y no cierra episodios.</p>
                  %s
                  <form method="post" action="/ward/login">
                    <label>Usuario <input name="username" autocomplete="username" required></label>
                    <label>Clave <input name="password" type="password" autocomplete="current-password" required>
                      <span class="help">Use la clave definida para esta demostración.</span></label>
                    <button class="btn btn-primary" type="submit">Entrar</button>
                  </form>
                </section></main></body></html>
                """.formatted(head(), alert(notice));
    }

    static String patients(WardPrincipal principal, String csrf, String notice, List<Map<String, Object>> patients) {
        StringBuilder rows = new StringBuilder();
        for (Map<String, Object> patient : patients) {
            String id = String.valueOf(patient.get("patient_id"));
            rows.append("<tr><td data-label=\"Paciente\"><a class=\"person\" href=\"/ward/patients/")
                    .append(esc(id)).append("\">")
                    .append(esc(String.valueOf(patient.get("given_name")))).append(" ")
                    .append(esc(String.valueOf(patient.get("family_name")))).append("</a></td>")
                    .append("<td data-label=\"Identificador\">").append(esc(id)).append("</td>")
                    .append("<td data-label=\"Registro\">Sintético</td></tr>");
        }
        String body = """
                <header class="hero"><p class="kicker">Censo</p><h1>Pacientes</h1>
                <p class="muted">Seleccione un paciente sintético para abrir o consultar una hospitalización.</p></header>
                <section class="panel"><table><thead><tr><th>Paciente</th><th>Identificador</th><th>Registro</th></tr></thead>
                <tbody>%s</tbody></table></section>
                """.formatted(rows);
        return layout("Pacientes", "patients", principal, csrf, notice, body);
    }

    static String patient(WardPrincipal principal, String csrf, String notice, Map<String, Object> patient) {
        String id = String.valueOf(patient.get("patient_id"));
        String name = patient.get("given_name") + " " + patient.get("family_name");
        String action = clinician(principal)
                ? form("/ward/patients/" + id + "/episodes", csrf, "<button class=\"btn btn-primary\" type=\"submit\">Abrir hospitalización</button>")
                : "<p class=\"muted\">Su rol puede consultar. No puede abrir una hospitalización.</p>";
        String body = """
                <header class="hero"><p class="kicker">Paciente sintético</p><h1>%s</h1>
                <p class="episode-code">%s</p><div class="hero-actions">%s</div></header>
                """.formatted(esc(name), esc(id), action);
        return layout("Paciente", "patients", principal, csrf, notice, body);
    }

    static String episodes(WardPrincipal principal, String csrf, String notice, List<Map<String, Object>> episodes) {
        StringBuilder rows = new StringBuilder();
        for (Map<String, Object> episode : episodes) {
            String id = String.valueOf(episode.get("episode_id"));
            rows.append("<tr><td data-label=\"Paciente\"><a href=\"/ward/episodes/").append(esc(id)).append("\">")
                    .append(esc(episode.get("given_name") + " " + episode.get("family_name"))).append("</a></td>")
                    .append("<td data-label=\"Episodio\" class=\"episode-code\">").append(esc(id)).append("</td>")
                    .append("<td data-label=\"Estado\">").append(status(episode.get("status"))).append("</td>")
                    .append("<td data-label=\"Ingreso\">").append(when(episode.get("opened_at"))).append("</td></tr>");
        }
        String empty = episodes.isEmpty() ? "<p class=\"muted\">Todavía no hay hospitalizaciones.</p>" : "";
        String body = """
                <header class="hero"><p class="kicker">Hospitalización</p><h1>Episodios</h1></header>
                <section class="panel">%s<table><thead><tr><th>Paciente</th><th>Episodio</th><th>Estado</th><th>Ingreso</th></tr></thead>
                <tbody>%s</tbody></table></section>
                """.formatted(empty, rows);
        return layout("Episodios", "episodes", principal, csrf, notice, body);
    }

    static String tasks(WardPrincipal principal, String csrf, String notice, List<Map<String, Object>> tasks) {
        String body = """
                <header class="hero"><p class="kicker">Trabajo pendiente</p><h1>Tareas</h1>
                <p class="muted">Una tarea de planta abierta impide declarar completa la preparación. El seguimiento no la bloquea.</p></header>
                <section class="panel">%s</section>
                """.formatted(taskTable(tasks, true));
        return layout("Tareas", "tasks", principal, csrf, notice, body);
    }

    static String auditIndex(WardPrincipal principal, String csrf, String notice, List<Map<String, Object>> rows) {
        String body = """
                <header class="hero"><p class="kicker">Evidencia</p><h1>Auditoría</h1>
                <p class="muted">Registro de las operaciones guardadas. No sustituye la ficha clínica.</p></header>
                <section class="panel">%s</section>
                """.formatted(auditTable(rows, true));
        return layout("Auditoría", "audit", principal, csrf, notice, body);
    }

    static String missing(WardPrincipal principal, String csrf, String notice, String title) {
        return layout(title, "patients", principal, csrf, notice, "<section class=\"panel\"><p>El registro no está disponible.</p></section>");
    }

    static String episode(WardPrincipal principal, String csrf, String notice, Map<String, Object> episode, Map<String, Object> patient) {
        String episodeId = String.valueOf(episode.get("episode_id"));
        String patientId = String.valueOf(episode.get("patient_id"));
        String name = patient.get("given_name") + " " + patient.get("family_name");
        int version = ((Number) episode.get("version")).intValue();
        boolean clinician = clinician(principal);
        Map<String, Object> checklist = map(episode.get("checklist"));
        boolean complete = Boolean.TRUE.equals(checklist.get("complete"));
        boolean wardOpen = rows(episode.get("tasks")).stream()
                .anyMatch(task -> "ward".equals(task.get("kind")) && "open".equals(task.get("status")));
        String next = wardOpen ? "#tareas" : "#preparacion";
        String nextLabel = wardOpen ? "Resolver tarea pendiente" : "Continuar preparación";
        String body = """
                <header class="hero">
                  <p class="kicker">Hospitalización</p>
                  <h1>%s</h1>
                  <p class="episode-code">Episodio %s</p>
                  <div class="meta">%s %s <span class="chip">Ingreso %s</span><span class="chip">%s</span>%s</div>
                  <div class="hero-actions"><a class="btn btn-primary" href="%s">%s</a></div>
                </header>
                <div class="tabs" role="tablist" aria-label="Ficha del episodio">
                  <button type="button" role="tab" data-tab="resumen" aria-selected="true">Resumen</button>
                  <button type="button" role="tab" data-tab="evolucion" aria-selected="false" tabindex="-1">Evolución</button>
                  <button type="button" role="tab" data-tab="resultados" aria-selected="false" tabindex="-1">Resultados</button>
                  <button type="button" role="tab" data-tab="tareas" aria-selected="false" tabindex="-1">Tareas</button>
                  <button type="button" role="tab" data-tab="preparacion" aria-selected="false" tabindex="-1">Preparación</button>
                  <button type="button" role="tab" data-tab="auditoria" aria-selected="false" tabindex="-1">Auditoría</button>
                </div>
                <section data-panel="resumen" id="resumen">%s</section>
                <section data-panel="evolucion" id="evolucion" hidden>%s</section>
                <section data-panel="resultados" id="resultados" hidden>%s</section>
                <section data-panel="tareas" id="tareas" hidden>%s</section>
                <section data-panel="preparacion" id="preparacion" hidden>%s</section>
                <section data-panel="auditoria" id="auditoria" hidden>%s</section>
                """.formatted(
                esc(name), esc(episodeId), status(episode.get("status")),
                complete ? "<span class=\"status status-ok\" id=\"checklist-state\">Preparación completa</span>"
                        : "<span class=\"status status-warning\" id=\"checklist-state\">Preparación incompleta</span>",
                when(episode.get("opened_at")), esc(String.valueOf(episode.get("organization_id"))),
                docStatus(episode.get("documentation_status")), next, esc(nextLabel),
                summary(episode, checklist, wardOpen),
                evolution(episode, clinician, csrf, episodeId, version),
                results(episode, clinician, csrf, episodeId, version),
                tasksPanel(episode, clinician, csrf, episodeId, version),
                preparation(episode, clinician, csrf, episodeId, version),
                auditPanel(episode, clinician, csrf, episodeId, version));
        return layout(name, "episodes", principal, csrf, notice, body);
    }

    private static String summary(Map<String, Object> episode, Map<String, Object> checklist, boolean wardOpen) {
        String reason = wardOpen
                ? "<p class=\"notice\" data-tone=\"warning\">Hay una tarea de planta abierta. Resuélvala para poder completar la preparación.</p>"
                : "";
        return """
                <div class="grid"><section class="card"><h2>Resumen clínico</h2><ul class="check">%s</ul></section>
                <section class="card"><h2>Línea de tiempo</h2>%s<ol class="timeline">%s</ol></section></div>
                """.formatted(checks(checklist), reason, timeline(episode));
    }

    private static String checks(Map<String, Object> checklist) {
        return item("Notas clínicas", checklist.get("notes"))
                + item("Resultados de laboratorio", checklist.get("results"))
                + item("Alergias", checklist.get("allergies"))
                + item("Medicación documentada", checklist.get("medications"))
                + item("Tareas de planta", checklist.get("pending"))
                + item("Revisión del borrador", checklist.get("documentation"));
    }

    private static String item(String label, Object done) {
        boolean ready = Boolean.TRUE.equals(done);
        return "<li><span>" + esc(label) + "</span><span class=\"status " + (ready ? "status-ok" : "status-warning")
                + "\">" + (ready ? "Completo" : "Pendiente") + "</span></li>";
    }

    private static String timeline(Map<String, Object> episode) {
        StringBuilder html = new StringBuilder();
        html.append(timeRow(episode.get("opened_at"), "Ingreso hospitalario", "Se abrió el episodio."));
        for (Map<String, Object> note : rows(episode.get("notes"))) {
            html.append(timeRow(note.get("created_at"), "Nota clínica", String.valueOf(note.get("body"))));
        }
        for (Map<String, Object> result : rows(episode.get("results"))) {
            html.append(timeRow(null, "Resultado asociado", result.get("display_name") + " " + result.get("value_text") + " " + result.get("unit")));
        }
        for (Map<String, Object> task : rows(episode.get("tasks"))) {
            String kind = "follow_up".equals(task.get("kind")) ? "Seguimiento" : "Tarea de planta";
            html.append(timeRow(task.get("created_at"), kind, String.valueOf(task.get("title"))));
        }
        return html.toString();
    }

    private static String evolution(Map<String, Object> episode, boolean clinician, String csrf, String episodeId, int version) {
        StringBuilder notes = new StringBuilder();
        for (Map<String, Object> note : rows(episode.get("notes"))) {
            notes.append("<article class=\"card\"><p class=\"muted\">").append(when(note.get("created_at")))
                    .append(" · ").append(esc(String.valueOf(note.get("author_id")))).append("</p><p>")
                    .append(esc(String.valueOf(note.get("body")))).append("</p><p class=\"episode-code\">")
                    .append(esc(String.valueOf(note.get("note_id")))).append("</p></article>");
        }
        String allergies = rows(episode.get("allergies")).stream()
                .map(row -> "<li>" + esc(String.valueOf(row.get("substance"))) + "</li>")
                .reduce("", String::concat);
        String medications = rows(episode.get("medications")).stream()
                .map(row -> "<li>" + esc(String.valueOf(row.get("name"))) + " · " + medStatus(row.get("documented_status")) + "</li>")
                .reduce("", String::concat);
        String forms = clinician ? form("/ward/episodes/" + episodeId + "/notes", csrf, """
                <input type="hidden" name="version" value="%d">
                <label>Nueva nota <textarea name="body" required maxlength="240"></textarea>
                <span class="help">Use letras, números y puntuación simple. El servidor rechaza otro contenido.</span></label>
                <button class="btn btn-primary" type="submit">Registrar nota</button>
                """.formatted(version))
                + form("/ward/patients/" + episode.get("patient_id") + "/allergies", csrf, """
                <input type="hidden" name="episodeId" value="%s">
                <label>Alergia sintética <input name="substance" required maxlength="240">
                <span class="help">Documenta una alergia de demostración. No es una prescripción.</span></label>
                <button class="btn btn-secondary" type="submit">Registrar alergia</button>
                """.formatted(esc(episodeId)))
                + form("/ward/patients/" + episode.get("patient_id") + "/medications", csrf, """
                <input type="hidden" name="episodeId" value="%s">
                <label>Medicación documentada <input name="name" required maxlength="240"></label>
                <label>Situación <select name="status"><option value="active">Vigente</option><option value="stopped">Suspendida</option></select></label>
                <button class="btn btn-secondary" type="submit">Registrar medicación</button>
                """.formatted(esc(episodeId))) : "";
        return "<div class=\"grid\"><section><h2>Notas clínicas</h2>" + notes + "</section><section class=\"stack\"><section class=\"card\"><h2>Alergias</h2><ul>"
                + allergies + "</ul></section><section class=\"card\"><h2>Medicación documentada</h2><ul>" + medications
                + "</ul></section>" + forms + "</section></div>";
    }

    private static String results(Map<String, Object> episode, boolean clinician, String csrf, String episodeId, int version) {
        StringBuilder linked = new StringBuilder();
        for (Map<String, Object> result : rows(episode.get("results"))) {
            linked.append("<tr><td data-label=\"Prueba\">").append(esc(String.valueOf(result.get("display_name"))))
                    .append("</td><td data-label=\"Valor\">").append(esc(result.get("value_text") + " " + result.get("unit")))
                    .append("</td><td data-label=\"Identificador\" class=\"episode-code\">")
                    .append(esc(String.valueOf(result.get("result_id")))).append("</td></tr>");
        }
        StringBuilder options = new StringBuilder();
        for (Map<String, Object> result : rows(episode.get("availableResults"))) {
            options.append("<option value=\"").append(esc(String.valueOf(result.get("result_id")))).append("\">")
                    .append(esc(String.valueOf(result.get("display_name")))).append("</option>");
        }
        String form = clinician && !options.isEmpty() ? form("/ward/episodes/" + episodeId + "/results", csrf, """
                <input type="hidden" name="version" value="%d">
                <label>Resultado ya registrado <select name="resultId">%s</select>
                <span class="help">Asocia un resultado sintético existente. No crea un valor nuevo.</span></label>
                <button class="btn btn-primary" type="submit">Asociar resultado</button>
                """.formatted(version, options)) : "";
        return "<section class=\"panel\"><h2>Resultados de laboratorio</h2><table><thead><tr><th>Prueba</th><th>Valor</th><th>Identificador</th></tr></thead><tbody>"
                + linked + "</tbody></table>" + form + "</section>";
    }

    private static String tasksPanel(Map<String, Object> episode, boolean clinician, String csrf, String episodeId, int version) {
        StringBuilder rows = new StringBuilder();
        for (Map<String, Object> task : rows(episode.get("tasks"))) {
            boolean wardOpen = clinician && "ward".equals(task.get("kind")) && "open".equals(task.get("status"));
            String action = wardOpen ? form("/ward/episodes/" + episodeId + "/tasks/" + task.get("task_id") + "/resolve", csrf,
                    "<input type=\"hidden\" name=\"version\" value=\"" + version + "\"><button class=\"btn btn-teal\" type=\"submit\">Resolver</button>") : "";
            rows.append("<tr><td data-label=\"Descripción\">").append(esc(String.valueOf(task.get("title"))))
                    .append("</td><td data-label=\"Tipo\">").append(taskKind(task.get("kind")))
                    .append("</td><td data-label=\"Estado\">").append(taskStatus(task.get("status")))
                    .append("</td><td data-label=\"Fecha\">").append(when(task.get("created_at")))
                    .append("</td><td data-label=\"Acción\">").append(action).append("</td></tr>");
        }
        String form = clinician ? form("/ward/episodes/" + episodeId + "/tasks", csrf, """
                <input type="hidden" name="version" value="%d">
                <label>Nueva tarea de planta <input name="title" required maxlength="240">
                <span class="help">Esta tarea bloquea la preparación hasta que se resuelva.</span></label>
                <button class="btn btn-primary" type="submit">Registrar pendiente</button>
                """.formatted(version)) : "";
        return "<section class=\"panel\"><h2>Tareas del episodio</h2><table><thead><tr><th>Descripción</th><th>Tipo</th><th>Estado</th><th>Fecha</th><th></th></tr></thead><tbody>"
                + rows + "</tbody></table>" + form + "</section>";
    }

    private static String preparation(Map<String, Object> episode, boolean clinician, String csrf, String episodeId, int version) {
        JsonNode proposal = proposal(episode.get("proposal"));
        String request = clinician ? form("/ward/episodes/" + episodeId + "/prepare", csrf,
                "<button class=\"btn btn-primary\" type=\"submit\">Solicitar preparación</button>") : "";
        if (proposal == null) {
            return "<section class=\"panel\"><h2>Preparación de alta</h2><p>Todavía no hay un borrador para este episodio.</p>" + request + "</section>";
        }
        boolean ready = proposal.path("checklistComplete").asBoolean(false);
        String phase = "accepted".equals(String.valueOf(episode.get("documentation_status")))
                ? "Borrador aceptado"
                : "PENDING_REVIEW".equals(proposal.path("phase").asText()) ? "Pendiente de revisión" : "Preparación registrada";
        StringBuilder statements = new StringBuilder();
        proposal.path("statements").forEach(statement -> statements.append("<blockquote class=\"quote\"><p>")
                .append(esc(statement.path("text").asText())).append("</p><p class=\"muted\">")
                .append(references(statement.path("sources"))).append("</p></blockquote>"));
        StringBuilder protocols = new StringBuilder();
        proposal.path("protocols").forEach(protocol -> protocols.append("<article class=\"card\"><h3>")
                .append(esc(protocolTitle(protocol.path("id").asText()))).append("</h3><p class=\"muted\">Versión ")
                .append(esc(protocol.path("version").asText())).append(" · ").append(esc(protocol.path("section").asText()))
                .append("</p><p>").append(esc(excerpt(protocol.path("text").asText()))).append("</p></article>"));
        boolean accepted = "accepted".equals(String.valueOf(map(episode.get("proposal")).get("checklist_complete")))
                || "accepted".equals(String.valueOf(episode.get("documentation_status")));
        String review = "";
        if (clinician && "proposed".equals(episode.get("documentation_status"))) {
            review = form("/ward/episodes/" + episodeId + "/decision", csrf, """
                    <div class="actions">
                      <button class="btn btn-primary" name="decision" value="approved" type="submit">Aprobar borrador</button>
                      <button class="btn btn-secondary" name="decision" value="changes_requested" type="submit">Solicitar corrección</button>
                      <button class="btn btn-secondary" name="decision" value="rejected" type="submit">Rechazar</button>
                    </div>
                    """);
        }
        String follow = clinician && accepted ? form("/ward/episodes/" + episodeId + "/follow-ups", csrf, """
                <input type="hidden" name="version" value="%d">
                <p class="help">Crea solo las tareas incluidas en el borrador aprobado. Repetir la acción no las duplica.</p>
                <button class="btn btn-teal" type="submit">Crear tareas de seguimiento</button>
                """.formatted(version)) : "";
        String simulation = "intercepted".equals(proposal.path("modelMode").asText())
                ? "<p class=\"banner\">El texto de preparación es una simulación local. No decide el alta ni cierra la hospitalización.</p>" : "";
        String pending = pendingTasks(proposal, episode);
        return """
                <section class="panel"><h2>Preparación de alta</h2>%s
                <div class="meta"><span class="status %s">%s</span><span class="chip">%s</span></div>
                %s%s<h2>Protocolos citados</h2>%s
                <section class="card"><h2>Revisión humana</h2>
                <p>Versión del episodio en la propuesta: %s. Aprobar el borrador no cierra la hospitalización.</p>
                %s%s</section>
                <details class="tech"><summary>Detalle técnico de la propuesta</summary>
                <p>Identificador %s</p><p>Versión del episodio %s</p><p class="episode-code">Huella %s</p></details>
                %s</section>
                """.formatted(simulation, ready ? "status-ok" : "status-warning",
                ready ? "Preparación lista para revisión" : "Preparación incompleta", esc(phase),
                statements, pending, protocols, proposal.path("episodeVersion").asText(), review, follow,
                esc(proposal.path("proposalId").asText()), esc(proposal.path("episodeVersion").asText()),
                esc(proposal.path("proposalHash").asText()), request);
    }

    private static String pendingTasks(JsonNode proposal, Map<String, Object> episode) {
        StringBuilder html = new StringBuilder();
        proposal.path("pending").forEach(node -> {
            String id = node.asText();
            String title = rows(episode.get("tasks")).stream()
                    .filter(task -> id.equals(task.get("task_id")))
                    .map(task -> String.valueOf(task.get("title")))
                    .findFirst().orElse(id);
            html.append("<li>").append(esc(title)).append("</li>");
        });
        if (html.isEmpty()) return "";
        return "<h2>Pendiente que bloquea la preparación</h2><ul>" + html + "</ul>";
    }

    private static String references(JsonNode sources) {
        StringBuilder html = new StringBuilder();
        sources.forEach(source -> {
            if (!html.isEmpty()) html.append(" · ");
            html.append(esc(sourceLabel(source.path("source").asText()))).append(" ").append(esc(source.path("id").asText()));
        });
        return html.toString();
    }

    private static String auditPanel(Map<String, Object> episode, boolean clinician, String csrf, String episodeId, int version) {
        String close = clinician && "open".equals(episode.get("status")) ? """
                <section class="card danger-zone"><h2>Cierre de hospitalización</h2>
                <p>Esta acción es independiente del borrador. Solo una persona autorizada puede cerrar el episodio.</p>
                %s</section>
                """.formatted(form("/ward/episodes/" + episodeId + "/close", csrf, """
                <input type="hidden" name="version" value="%d">
                <button class="btn btn-danger" type="submit">Cerrar episodio</button>
                """.formatted(version))) : "";
        return "<section class=\"panel\" id=\"audit\"><h2>Auditoría del episodio</h2>" + auditTable(rows(episode.get("audit")), false)
                + "</section>" + close;
    }

    private static String taskTable(List<Map<String, Object>> tasks, boolean linkEpisode) {
        StringBuilder rows = new StringBuilder();
        for (Map<String, Object> task : tasks) {
            String episode = String.valueOf(task.get("episode_id"));
            String title = linkEpisode ? "<a href=\"/ward/episodes/" + esc(episode) + "#tareas\">" + esc(String.valueOf(task.get("title"))) + "</a>"
                    : esc(String.valueOf(task.get("title")));
            rows.append("<tr><td data-label=\"Descripción\">").append(title)
                    .append("</td><td data-label=\"Tipo\">").append(taskKind(task.get("kind")))
                    .append("</td><td data-label=\"Estado\">").append(taskStatus(task.get("status")))
                    .append("</td><td data-label=\"Fecha\">").append(when(task.get("created_at")))
                    .append("</td><td data-label=\"Episodio\" class=\"episode-code\">").append(esc(episode)).append("</td></tr>");
        }
        return "<table><thead><tr><th>Descripción</th><th>Tipo</th><th>Estado</th><th>Fecha</th><th>Episodio</th></tr></thead><tbody>" + rows + "</tbody></table>";
    }

    private static String auditTable(List<Map<String, Object>> rows, boolean includeEpisode) {
        StringBuilder html = new StringBuilder("<table><thead><tr><th>Fecha</th><th>Usuario</th><th>Operación</th><th>Resultado</th><th>Identificador</th>");
        if (includeEpisode) html.append("<th>Episodio</th>");
        html.append("</tr></thead><tbody>");
        for (Map<String, Object> row : rows) {
            html.append("<tr><td data-label=\"Fecha\">").append(when(row.get("recorded_at")))
                    .append("</td><td data-label=\"Usuario\">").append(esc(String.valueOf(row.get("actor_id"))))
                    .append("</td><td data-label=\"Operación\">").append(esc(actionLabel(row.get("action"))))
                    .append("<details class=\"tech\"><summary>Detalle técnico</summary><p>")
                    .append(esc(String.valueOf(row.get("action")))).append(" · ")
                    .append(esc(String.valueOf(row.get("outcome")))).append(" · ")
                    .append(esc(String.valueOf(row.get("detail")))).append("</p></details></td><td data-label=\"Resultado\">")
                    .append(esc(outcomeLabel(row.get("outcome")))).append("</td><td data-label=\"Identificador\" class=\"episode-code\">")
                    .append(esc(String.valueOf(row.get("detail")))).append("</td>");
            if (includeEpisode) {
                html.append("<td data-label=\"Episodio\"><a href=\"/ward/episodes/").append(esc(String.valueOf(row.get("episode_id"))))
                        .append("\">").append(esc(String.valueOf(row.get("episode_id")))).append("</a></td>");
            }
            html.append("</tr>");
        }
        return html + "</tbody></table>";
    }

    private static String layout(String title, String active, WardPrincipal principal, String csrf, String notice, String body) {
        String session = principal == null ? "" : """
                <div class="session"><span>%s · %s · %s</span>%s</div>
                """.formatted(esc(roleLabel(principal.role())), esc(principal.userId()), esc(principal.organizationId()),
                form("/ward/logout", csrf, "<button class=\"btn btn-secondary\" type=\"submit\">Cerrar sesión</button>"));
        return """
                <!DOCTYPE html>
                <html lang="es"><head>%s<title>%s</title></head><body>
                <a class="skip" href="#contenido">Saltar al contenido</a>
                <header class="topbar"><div class="topbar-inner"><a class="brand" href="/ward/patients"><span class="mark" aria-hidden="true"></span><span><strong>Healthcare Lab</strong><span>Mini HIS</span></span></a>%s</div></header>
                <nav class="nav" aria-label="Principal"><div class="nav-inner">%s</div></nav>
                <main class="page" id="contenido">%s%s</main>
                <script src="/ward/app.js"></script></body></html>
                """.formatted(head(), esc(title), session, nav(active), alert(notice), body);
    }

    private static String nav(String active) {
        return link("patients", "/ward/patients", "Pacientes", active)
                + link("episodes", "/ward/episodes", "Episodios", active)
                + link("tasks", "/ward/tasks", "Tareas", active)
                + link("audit", "/ward/audit", "Revisión y auditoría", active);
    }

    private static String link(String key, String href, String label, String active) {
        String current = key.equals(active) ? " aria-current=\"page\"" : "";
        return "<a href=\"" + href + "\"" + current + ">" + label + "</a>";
    }

    private static String head() {
        return """
                <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
                <link rel="stylesheet" href="/ward/app.css">
                """;
    }

    private static String form(String action, String csrf, String fields) {
        return "<form method=\"post\" action=\"" + esc(action) + "\"><input type=\"hidden\" name=\"csrf\" value=\""
                + esc(csrf) + "\">" + fields + "</form>";
    }

    private static String alert(String code) {
        if (code == null || code.isBlank()) return "";
        String tone = switch (code) {
            case "version-conflicto", "no-autorizado", "coordinador-no-disponible", "entrada-invalida", "aprobacion-invalida", "sesion", "credenciales" -> "warning";
            default -> "ok";
        };
        return "<p class=\"notice\" id=\"notice\" data-tone=\"" + tone + "\">" + esc(message(code)) + "</p>";
    }

    static String message(String code) {
        return switch (code) {
            case "nota-registrada" -> "La nota quedó registrada.";
            case "alergia-registrada" -> "La alergia quedó registrada.";
            case "medicacion-registrada" -> "La medicación documentada quedó registrada.";
            case "resultado-asociado" -> "El resultado quedó asociado al episodio.";
            case "tarea-abierta" -> "La tarea de planta quedó pendiente.";
            case "tarea-resuelta" -> "La tarea de planta quedó resuelta.";
            case "preparacion-lista" -> "La preparación está lista para revisión.";
            case "preparacion-pendiente" -> "La preparación no se completó. Revise los datos del episodio.";
            case "decision-registrada" -> "La decisión quedó registrada. El episodio sigue abierto.";
            case "seguimiento-creado" -> "Las tareas de seguimiento autorizadas quedaron registradas.";
            case "episodio-cerrado" -> "La hospitalización quedó cerrada.";
            case "episodio-abierto" -> "La hospitalización quedó abierta.";
            case "version-conflicto" -> "La versión del episodio cambió. Actualice la ficha antes de continuar.";
            case "no-autorizado" -> "Esta operación no está autorizada para su rol.";
            case "coordinador-no-disponible" -> "El coordinador de alta no respondió. No se creó un borrador.";
            case "entrada-invalida" -> "Los datos no superaron la validación. Corrija el formulario.";
            case "aprobacion-invalida" -> "La decisión no corresponde a la propuesta vigente.";
            case "ya-registrado" -> "Esa operación ya estaba registrada.";
            case "sesion" -> "La sesión caducó. Vuelva a entrar.";
            case "credenciales" -> "No se pudo iniciar la sesión.";
            default -> "Operación registrada.";
        };
    }

    private static JsonNode proposal(Object stored) {
        Object raw = map(stored).get("body_json");
        if (!(raw instanceof String text) || text.isBlank()) return null;
        try {
            return JSON.readTree(text);
        } catch (Exception ex) {
            return null;
        }
    }

    private static String sourceLabel(String source) {
        return switch (source) {
            case "mini-his" -> "Ficha";
            case "protocol" -> "Protocolo";
            default -> source;
        };
    }

    private static String excerpt(String text) {
        if (text == null || text.isBlank()) {
            return "";
        }
        StringBuilder kept = new StringBuilder();
        for (String line : text.split("\\R")) {
            String trimmed = line.strip();
            if (trimmed.isEmpty() || trimmed.startsWith("#")) {
                continue;
            }
            if (!kept.isEmpty()) {
                kept.append(' ');
            }
            kept.append(trimmed);
        }
        return kept.toString();
    }

    private static String protocolTitle(String id) {
        return switch (id) {
            case "discharge-preparation" -> "Preparación de alta";
            case "pending-verification" -> "Verificación de pendientes";
            case "continuity" -> "Continuidad asistencial";
            case "follow-up-coordination" -> "Coordinación de seguimiento";
            case "documentation-review" -> "Revisión de documentación";
            default -> id;
        };
    }

    private static String actionLabel(Object action) {
        return switch (String.valueOf(action)) {
            case "episode_opened" -> "Hospitalización abierta";
            case "note_recorded" -> "Nota registrada";
            case "result_linked" -> "Resultado asociado";
            case "task_opened" -> "Tarea registrada";
            case "task_resolved" -> "Tarea resuelta";
            case "documentation_accepted" -> "Borrador aceptado";
            case "follow_up_created" -> "Seguimiento creado";
            case "episode_closed" -> "Hospitalización cerrada";
            default -> String.valueOf(action);
        };
    }

    private static String outcomeLabel(Object outcome) {
        return "recorded".equals(outcome) ? "Registrado" : String.valueOf(outcome);
    }

    private static String status(Object value) {
        boolean open = "open".equals(value);
        return "<span class=\"status " + (open ? "status-open" : "status-closed") + "\">" + (open ? "Abierto" : "Cerrado") + "</span>";
    }

    private static String docStatus(Object value) {
        String label = switch (String.valueOf(value)) {
            case "accepted" -> "Documentación aceptada";
            case "proposed" -> "Borrador propuesto";
            default -> "Sin borrador";
        };
        return "<span class=\"chip\">" + label + "</span>";
    }

    private static String medStatus(Object value) {
        return "stopped".equals(value) ? "Suspendida" : "Vigente";
    }

    private static String taskKind(Object value) {
        return "follow_up".equals(value) ? "Seguimiento" : "Planta";
    }

    private static String taskStatus(Object value) {
        boolean open = "open".equals(value);
        return "<span class=\"status " + (open ? "status-warning" : "status-ok") + "\">" + (open ? "Pendiente" : "Resuelto") + "</span>";
    }

    private static String roleLabel(String role) {
        return "auditor".equals(role) ? "Auditor" : "Clínico";
    }

    private static String timeRow(Object at, String title, String detail) {
        return "<li><span class=\"when\">" + when(at) + "</span><span><strong>" + esc(title) + "</strong><br>" + esc(detail) + "</span></li>";
    }

    private static String when(Object value) {
        if (value == null) return "";
        try {
            return WHEN.format(OffsetDateTime.parse(String.valueOf(value)));
        } catch (Exception ex) {
            return esc(String.valueOf(value));
        }
    }

    private static boolean clinician(WardPrincipal principal) {
        return principal != null && "clinician".equals(principal.role());
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> rows(Object value) {
        return value instanceof List<?> list ? (List<Map<String, Object>>) list : List.of();
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> map(Object value) {
        return value instanceof Map<?, ?> map ? (Map<String, Object>) map : Map.of();
    }

    private static String esc(String value) {
        return value == null ? "" : value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;");
    }
}
