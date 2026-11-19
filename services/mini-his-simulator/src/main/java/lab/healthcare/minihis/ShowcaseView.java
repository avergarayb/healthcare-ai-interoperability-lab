package lab.healthcare.minihis;

import java.util.List;

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
                .append(esc(title(id))).append("</h1><p>").append(esc(pitch(id))).append("</p></section>");
        body.append("<section class=\"card\"><h2>Recorrido</h2><ol class=\"steps\">");
        for (ShowcaseCatalog.Step step : steps) {
            body.append("<li><a href=\"").append(esc(step.href())).append("\">").append(esc(step.label())).append("</a> ");
            body.append(step.done() ? "<span class=\"status status-ok\">Comprobado</span>" : "<span class=\"status status-warning\">Pendiente</span>");
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
