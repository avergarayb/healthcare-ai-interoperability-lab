package lab.healthcare.minihis;

import java.util.List;
import java.util.Map;

final class ShowcaseView {

    private ShowcaseView() {
    }

    static String index(List<ShowcaseCatalog.Card> cards) {
        StringBuilder body = new StringBuilder();
        body.append("""
                <section class="hero"><p class="kicker">Healthcare Lab</p><h1>Demostraciones clínicas</h1>
                <p>Cinco recorridos ya integrados. Esta pantalla no crea agentes ni eleva permisos.</p></section>
                <div class="grid">
                """);
        for (ShowcaseCatalog.Card card : cards) {
            body.append("<article class=\"panel\"><p class=\"kicker\">").append(esc(card.availability())).append("</p><h2>")
                    .append(esc(card.name())).append("</h2><p>").append(esc(card.problem())).append("</p><p>")
                    .append(esc(card.systems())).append("</p><p>").append(esc(card.capabilities())).append("</p><p><a class=\"btn btn-primary\" href=\"")
                    .append(esc(card.actionHref())).append("\">").append(esc(card.actionLabel())).append("</a></p></article>");
        }
        body.append("</div>");
        return page("Portal", body.toString());
    }

    static String demo(String id, String availability, List<ShowcaseCatalog.Step> steps, List<String> trace, String csrf) {
        StringBuilder body = new StringBuilder();
        body.append("<p><a href=\"/showcase\">Volver al portal</a></p>");
        body.append("<section class=\"hero\"><p class=\"kicker\">").append(esc(availability)).append("</p><h1>")
                .append(esc(title(id))).append("</h1><p>").append(esc(pitch(id))).append("</p>");
        if ("demo-001".equals(id)) {
            body.append("<p><a class=\"btn btn-primary\" href=\"/showcase/demo-001/case\">Preparar resumen</a></p>");
        }
        body.append("</section>");
        body.append("<section class=\"card\"><h2>Recorrido</h2><ol class=\"steps\">");
        for (ShowcaseCatalog.Step step : steps) {
            body.append("<li><a href=\"").append(esc(step.href())).append("\">").append(esc(step.label())).append("</a> ");
            body.append(step.done()
                    ? "<span class=\"status status-ok\">Comprobado</span>"
                    : "<span class=\"status status-warning\">" + esc(step.openLabel()) + "</span>");
            body.append("<p class=\"muted\">").append(esc(step.evidence())).append("</p></li>");
        }
        body.append("</ol></section>");
        if ("demo-005".equals(id) && !csrf.isBlank()) {
            body.append("<section class=\"card\"><h2>Caso nuevo</h2><p>Abre otro episodio del paciente sintético. No borra los anteriores.</p><form method=\"post\" action=\"/ward/showcase/episode\"><input type=\"hidden\" name=\"csrf\" value=\"")
                    .append(esc(csrf)).append("\"><button class=\"btn btn-primary\" type=\"submit\">Preparar episodio</button></form></section>");
        } else if ("demo-005".equals(id)) {
            body.append("<section class=\"card\"><h2>Caso nuevo</h2><p>La preparación exige la sesión local de clínico. No es OIDC.</p><p><a class=\"btn btn-primary\" href=\"/ward/login\">Entrar</a></p></section>");
        }
        body.append("<section class=\"card\"><h2>Qué decide una persona</h2><p>").append(esc(human(id))).append("</p></section>");
        body.append("<details class=\"tech\"><summary>Trazabilidad</summary><ul>");
        for (String line : trace) {
            body.append("<li>").append(esc(line)).append("</li>");
        }
        body.append("</ul></details>");
        return page(title(id), body.toString());
    }

    static String summaryHome(PatientView patient, List<LabOrderView> orders, boolean clinician, String csrf, String notice) {
        StringBuilder body = new StringBuilder();
        body.append("<p><a href=\"/showcase/demo-001\">Volver a DEMO-001</a></p>");
        body.append("<section class=\"hero\"><p class=\"kicker\">Modelo interceptado</p><h1>Resumen de laboratorio</h1>");
        body.append("<p>El texto sale del agente lab-result-summary-v1. El modelo no llama a un proveedor.</p></section>");
        notice(body, notice);
        body.append("<section class=\"card\"><h2>Paciente sintético</h2><p>")
                .append(esc(patient.givenName())).append(" ").append(esc(patient.familyName()))
                .append("</p><p class=\"muted\">").append(esc(patient.patientId())).append(" · org-mini-his</p>");
        body.append("<p><a href=\"/ward/patients/").append(esc(patient.patientId())).append("\">Abrir la ficha</a></p></section>");
        body.append("<section class=\"card\"><h2>Órdenes locales</h2>");
        if (orders.isEmpty()) {
            body.append("<p>Este expediente todavía no tiene órdenes de laboratorio.</p>");
        } else {
            body.append("<ul>");
            for (LabOrderView order : orders) {
                body.append("<li>").append(esc(order.orderId())).append(" · ").append(esc(order.testCode()))
                        .append(" · ").append(esc(order.localStatus())).append("</li>");
            }
            body.append("</ul>");
        }
        body.append("</section>");
        if (clinician && !csrf.isBlank()) {
            body.append("<section class=\"card\"><h2>Caso nuevo</h2><p>Crea un identificador y un permiso que no se reutiliza.</p>");
            body.append("<form method=\"post\" action=\"/showcase/demo-001/case\"><input type=\"hidden\" name=\"csrf\" value=\"")
                    .append(esc(csrf)).append("\"><button class=\"btn btn-primary\" type=\"submit\">Ejecutar resumen</button></form></section>");
        } else {
            body.append("<section class=\"card\"><h2>Caso nuevo</h2><p>Solo el clínico de esta sesión puede ejecutarlo. El auditor no. No es OIDC.</p></section>");
        }
        return page("Resumen de laboratorio", body.toString());
    }

    static String summaryResult(Map<String, Object> view, boolean clinician, String csrf, String notice) {
        StringBuilder body = new StringBuilder();
        String caseId = text(view.get("caseId"));
        body.append("<p><a href=\"/showcase/demo-001/case\">Otro caso</a></p>");
        body.append("<section class=\"hero\"><p class=\"kicker\">Modelo interceptado</p><h1>Caso ").append(esc(caseId)).append("</h1>");
        body.append("<p>Paciente ").append(esc(text(view.get("patientId")))).append(" · ")
                .append(esc(text(view.get("organizationId")))).append("</p>");
        body.append("<p>La generación permanece interceptada. No es una respuesta prefabricada ni una llamada a un proveedor.</p></section>");
        notice(body, notice);
        body.append("<section class=\"card\"><h2>Resultados vigentes</h2>");
        facts(body, view.get("current"), "No hay un resultado vigente en esta ejecución.");
        body.append("</section><section class=\"card\"><h2>Observaciones históricas</h2>");
        facts(body, view.get("historical"), "No hay observaciones históricas distintas de este caso.");
        String reviewLine = view.get("decision") instanceof Map<?, ?> decision && present(decision.get("decision"))
                ? "Decisión registrada."
                : "Pendiente de revisión humana.";
        body.append("</section><section class=\"card\"><h2>Resumen del agente</h2><p class=\"muted\">")
                .append(esc(reviewLine)).append("</p>");
        if (view.get("statements") instanceof List<?> statements && !statements.isEmpty()) {
            body.append("<ul>");
            for (Object item : statements) {
                if (item instanceof Map<?, ?> statement) {
                    body.append("<li>").append(esc(text(statement.get("text")))).append("</li>");
                }
            }
            body.append("</ul>");
        } else {
            body.append("<p>El agente no dejó un resumen.</p>");
        }
        body.append("</section><section class=\"card\"><h2>Revisión humana</h2>");
        body.append("<p>Revisor de laboratorio: ").append(esc(text(view.get("reviewer"))))
                .append(". Autenticador de desarrollo. No es OIDC.</p>");
        if (view.get("decision") instanceof Map<?, ?> decision && present(decision.get("decision"))) {
            body.append("<p class=\"status status-ok\">").append(esc(text(decision.get("decision")))).append("</p>");
            body.append("<p>").append(esc(text(decision.get("note")))).append("</p>");
            body.append("<p class=\"muted\">").append(esc(text(decision.get("decidedAt")))).append("</p>");
        } else if (clinician && !csrf.isBlank()) {
            body.append("<p>Propuesta pendiente.</p><form method=\"post\" action=\"/showcase/demo-001/case/")
                    .append(esc(caseId)).append("/decision\"><input type=\"hidden\" name=\"csrf\" value=\"").append(esc(csrf)).append("\">");
            body.append("<button class=\"btn btn-primary\" type=\"submit\" name=\"decision\" value=\"approved\">Aprobar</button> ");
            body.append("<button class=\"btn\" type=\"submit\" name=\"decision\" value=\"rejected\">Rechazar</button></form>");
        } else {
            body.append("<p>Propuesta pendiente. Solo el clínico de esta sesión puede decidir.</p>");
        }
        body.append("</section>");
        if (clinician && !csrf.isBlank()) {
            body.append("<section class=\"card\"><h2>Permiso consumido</h2><p>Repetir este caso debe rechazarse. Un caso nuevo usa otro permiso.</p>");
            body.append("<form method=\"post\" action=\"/showcase/demo-001/case/").append(esc(caseId))
                    .append("/replay\"><input type=\"hidden\" name=\"csrf\" value=\"").append(esc(csrf))
                    .append("\"><button class=\"btn\" type=\"submit\">Repetir este permiso</button></form></section>");
        }
        body.append("<details class=\"tech\"><summary>Detalle técnico</summary>");
        body.append("<p>Herramienta MCP: ").append(esc(text(view.get("tool")))).append("</p>");
        body.append("<p>Grafo: ").append(esc(text(view.get("graph")))).append(" · estado ")
                .append(esc(text(view.get("phase")))).append("</p>");
        body.append("<p>Operación: ").append(esc(text(view.get("operation")))).append("</p>");
        body.append("<p>Correlación: ").append(esc(text(view.get("correlationId")))).append("</p>");
        body.append("<p>Revisión: ").append(esc(text(view.get("reviewId")))).append("</p>");
        body.append("<h3>Recursos consultados</h3>");
        facts(body, view.get("current"), "");
        facts(body, view.get("historical"), "");
        facts(body, view.get("reports"), "Sin informes en esta lectura.");
        body.append("<h3>Auditoría</h3><ul>");
        if (view.get("audit") instanceof List<?> audit) {
            for (Object item : audit) {
                if (item instanceof Map<?, ?> line) {
                    body.append("<li>").append(esc(text(line.get("event")))).append(" · ")
                            .append(esc(text(line.get("outcome")))).append(" · ")
                            .append(esc(text(line.get("actor")))).append("</li>");
                }
            }
        }
        body.append("</ul></details>");
        return page("Resumen de laboratorio", body.toString());
    }

    private static void notice(StringBuilder body, String notice) {
        if (notice == null || notice.isBlank()) {
            return;
        }
        body.append("<section class=\"card\"><p class=\"status status-warning\">").append(esc(noticeText(notice))).append("</p></section>");
    }

    private static String noticeText(String code) {
        return switch (code) {
            case "summary_unconfigured", "summary_unavailable" -> "El servicio de resumen no está disponible.";
            case "replay_denied" -> "Ese permiso ya se consumió. Prepara un caso nuevo.";
            case "already_decided" -> "Esa revisión ya tiene una decisión.";
            case "role_denied", "organization_denied", "unauthorized" -> "Esta sesión no puede ejecutar el resumen.";
            case "federation_unconfigured" -> "La federación no está configurada en el servicio.";
            case "context_incomplete" -> "La federación no entregó un contexto completo de ambas fuentes.";
            case "context_rejected" -> "El contexto federado no cumple el contrato del resumen.";
            case "not_found" -> "Ese caso no está en esta sesión.";
            default -> "El resumen no se completó.";
        };
    }

    private static void facts(StringBuilder body, Object value, String empty) {
        if (!(value instanceof List<?> facts) || facts.isEmpty()) {
            if (!empty.isBlank()) {
                body.append("<p>").append(esc(empty)).append("</p>");
            }
            return;
        }
        body.append("<ul>");
        for (Object item : facts) {
            if (item instanceof Map<?, ?> fact) {
                body.append("<li>").append(esc(text(fact.get("source")))).append(" · ")
                        .append(esc(text(fact.get("kind")))).append(" · ")
                        .append(esc(text(fact.get("id")))).append(" · ")
                        .append(esc(text(fact.get("code")))).append(" ")
                        .append(esc(text(fact.get("value")))).append(" ")
                        .append(esc(text(fact.get("unit")))).append("</li>");
            }
        }
        body.append("</ul>");
    }

    private static String text(Object value) {
        return value == null || String.valueOf(value).isBlank() || "null".equals(String.valueOf(value))
                ? "Sin dato" : String.valueOf(value);
    }

    private static boolean present(Object value) {
        return value != null && !String.valueOf(value).isBlank() && !"null".equals(String.valueOf(value));
    }

    static String missing() {
        return page("Demostración", "<section class=\"card\"><h1>Esa demostración no está en el portal.</h1><p><a href=\"/showcase\">Volver</a></p></section>");
    }

    private static String title(String id) {
        return switch (id) {
            case "demo-001" -> "Resumen de laboratorio";
            case "demo-002" -> "Comparación longitudinal";
            case "demo-003" -> "Interoperabilidad HL7/FHIR";
            case "demo-004" -> "Resultado crítico";
            case "demo-005" -> "Preparación de alta";
            default -> "Demostración";
        };
    }

    private static String pitch(String id) {
        return switch (id) {
            case "demo-001" -> "El problema es reunir el resultado del hospital y el del laboratorio. La interoperabilidad los federá. Una persona acepta el texto. No es un producto certificado ni una conexión con Epic u Oracle.";
            case "demo-002" -> "El problema es comparar dos fechas en dos países. Cada perfil conserva su organización y su OIDC. Esta sesión de laboratorio no entra en esos permisos.";
            case "demo-003" -> "El problema es perder la correlación entre la orden y el resultado. HL7 v2.5.1 y FHIR R4 son el intercambio de este laboratorio.";
            case "demo-004" -> "El problema es que un valor crítico no llegue a reconocerse. La regla es determinista. La persona aprueba la tarea interna.";
            case "demo-005" -> "El problema es preparar el egreso con tareas abiertas. El borrador cita protocolos. Aprobar no cierra el episodio.";
            default -> "";
        };
    }

    private static String human(String id) {
        return switch (id) {
            case "demo-002" -> "La aprueba el revisor del país, dentro de ese perfil.";
            case "demo-001", "demo-004", "demo-005" -> "La propuesta no autoriza. La decisión la registra una persona con el rol correspondiente.";
            default -> "El intercambio no sustituye la revisión del resumen, que sigue siendo una decisión humana.";
        };
    }

    private static String page(String title, String body) {
        return """
                <!DOCTYPE html>
                <html lang="es"><head>
                <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
                <link rel="stylesheet" href="/ward/app.css">
                <title>%s</title></head><body>
                <a class="skip" href="#contenido">Saltar al contenido</a>
                <header class="topbar"><div class="topbar-inner"><a class="brand" href="/showcase"><span class="mark" aria-hidden="true"></span><span><strong>Healthcare Lab</strong><span>Portal de demostración</span></span></a></div></header>
                <nav class="nav" aria-label="Principal"><div class="nav-inner"><a href="/showcase" aria-current="page">Portal</a><a href="/ward/login">Mini HIS</a><a href="/ward/orders">Órdenes</a><a href="/ward/episodes">Episodios</a></div></nav>
                <main class="page" id="contenido">%s</main></body></html>
                """.formatted(esc(title), body);
    }

    private static String esc(String value) {
        return value == null ? "" : value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;");
    }
}
