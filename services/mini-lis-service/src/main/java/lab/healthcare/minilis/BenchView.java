package lab.healthcare.minilis;

import java.util.List;
import java.util.Map;

final class BenchView {

    private BenchView() {
    }

    static String login(String notice) {
        return login(notice, false);
    }

    static String login(String notice, boolean oidc) {
        if (oidc) {
            return """
                    <!DOCTYPE html>
                    <html lang="es"><head>%s<title>Ingreso de laboratorio</title></head>
                    <body><main class="login-wrap" id="contenido"><section class="card login-card">
                      <p class="kicker">Healthcare Lab</p><h1>Mini LIS</h1>
                      <p class="muted">El ingreso de aceptación usa el proveedor OIDC del laboratorio. Esta página no acepta la clave local.</p>
                      %s
                      <p><a class="btn btn-primary" href="/oauth2/authorization/bench">Continuar al proveedor</a></p>
                    </section></main></body></html>
                    """.formatted(head(), alert(notice));
        }
        return loginForm(notice);
    }

    private static String loginForm(String notice) {
        return """
                <!DOCTYPE html>
                <html lang="es"><head>%s<title>Ingreso de laboratorio</title></head>
                <body><a class="skip" href="#contenido">Saltar al contenido</a>
                <main class="login-wrap" id="contenido"><section class="card login-card">
                  <p class="kicker">Healthcare Lab</p>
                  <h1>Mini LIS</h1>
                  <p class="muted">Sesión local de laboratorio en este equipo. No es OIDC ni un segundo realm.</p>
                  %s
                  <form method="post" action="/bench/login">
                    <label>Usuario <input name="username" autocomplete="username" required></label>
                    <label>Clave <input name="password" type="password" autocomplete="current-password" required></label>
                    <button class="btn btn-primary" type="submit">Entrar</button>
                  </form>
                </section></main></body></html>
                """.formatted(head(), alert(notice));
    }

    static String orders(
            BenchController.BenchPrincipal principal,
            String csrf,
            String notice,
            String view,
            List<LabOrder> orders,
            Map<String, String> states,
            Map<String, String> names) {
        StringBuilder rows = new StringBuilder();
        for (LabOrder order : orders) {
            String state = states.getOrDefault(order.orderId(), "ORDER_RECEIVED");
            if (!visible(view, state)) {
                continue;
            }
            rows.append("<tr><td data-label=\"HIS\">").append(esc(order.externalRequestId()))
                    .append("</td><td data-label=\"LIS\">").append(esc(order.orderId()))
                    .append("</td><td data-label=\"Paciente\">").append(esc(names.getOrDefault(order.patientId(), order.patientId())))
                    .append("</td><td data-label=\"Prueba\">").append(esc(order.testCode()))
                    .append("</td><td data-label=\"Fecha\">").append(esc(String.valueOf(order.requestedAt())))
                    .append("</td><td data-label=\"Estado\">").append(esc(label(state)))
                    .append("</td><td data-label=\"Correlación\">").append(esc(order.requestingOrganizationId()))
                    .append("</td><td><a href=\"/bench/orders/").append(esc(order.orderId())).append("\">Abrir</a></td></tr>");
        }
        if (rows.isEmpty()) {
            rows.append("<tr><td colspan=\"8\">No hay órdenes en esta vista.</td></tr>");
        }
        return page(principal, csrf, "orders", notice, "Órdenes de laboratorio", """
                <section class="card"><table>
                  <thead><tr><th>HIS</th><th>LIS</th><th>Paciente</th><th>Prueba</th><th>Fecha</th><th>Estado</th><th>Organización</th><th></th></tr></thead>
                  <tbody>%s</tbody>
                </table></section>
                """.formatted(rows));
    }

    static String order(
            BenchController.BenchPrincipal principal,
            String csrf,
            String notice,
            LabOrder order,
            ExternalPatient patient,
            BenchWorkflow.BenchCase bench,
            Map<String, Object> event,
            int resultCount) {
        String state = bench == null ? "ORDER_RECEIVED" : bench.state();
        String eventText = event == null
                ? "Sin evento crítico."
                : "Regla de simulación " + event.get("rule_id") + " " + event.get("rule_version")
                + ". Valor " + event.get("current_value") + " " + event.get("unit")
                + ". Correlación " + event.get("correlation_id") + ".";
        return page(principal, csrf, "orders", notice, "Orden " + order.orderId(), """
                <section class="hero">
                  <p class="kicker">Mini LIS</p>
                  <h1>%s</h1>
                  <p>%s · %s</p>
                  <div class="meta"><span class="status">%s</span><span class="chip">HIS %s</span><span class="chip">%s</span></div>
                </section>
                <section class="grid">
                  <article class="card"><h2>Muestra</h2><p>%s</p>%s</article>
                  <article class="card"><h2>Resultado</h2><p>%s</p><p class="muted">Resultados persistidos: %d. Un reintento no crea otro resultado.</p>%s</article>
                </section>
                <section class="card"><h2>Alerta determinista</h2><p>%s</p>
                  <p class="muted">La regla no depende del modelo. El mensaje HL7 no se muestra en esta ficha.</p></section>
                """.formatted(
                esc(patient.givenName() + " " + patient.familyName()),
                esc(order.testCode()),
                esc(order.testDescription()),
                esc(label(state)),
                esc(order.externalRequestId()),
                esc(order.requestingOrganizationId()),
                esc(bench == null || bench.specimenId() == null ? "La muestra todavía no está registrada." : bench.specimenId()),
                actions(csrf, order.orderId(), state, principal.validator()),
                esc(bench == null || bench.draftValue() == null ? "Sin valor." : bench.draftValue() + " " + bench.draftUnit()),
                resultCount,
                resultActions(csrf, order.orderId(), state, principal.validator()),
                esc(eventText)));
    }

    static String audit(BenchController.BenchPrincipal principal, String csrf, String notice, List<Map<String, Object>> events) {
        StringBuilder rows = new StringBuilder();
        for (Map<String, Object> event : events) {
            rows.append("<tr><td data-label=\"Evento\">").append(esc(String.valueOf(event.get("event_id"))))
                    .append("</td><td data-label=\"Orden\">").append(esc(String.valueOf(event.get("order_id"))))
                    .append("</td><td data-label=\"Regla\">").append(esc(String.valueOf(event.get("rule_id"))))
                    .append(" ").append(esc(String.valueOf(event.get("rule_version"))))
                    .append("</td><td data-label=\"Valor\">").append(esc(String.valueOf(event.get("current_value"))))
                    .append(" ").append(esc(String.valueOf(event.get("unit"))))
                    .append("</td><td data-label=\"Correlación\">").append(esc(String.valueOf(event.get("correlation_id"))))
                    .append("</td></tr>");
        }
        if (rows.isEmpty()) {
            rows.append("<tr><td colspan=\"5\">No hay eventos críticos.</td></tr>");
        }
        return page(principal, csrf, "audit", notice, "Auditoría de alertas", """
                <section class="card"><table>
                  <thead><tr><th>Evento</th><th>Orden</th><th>Regla</th><th>Valor</th><th>Correlación</th></tr></thead>
                  <tbody>%s</tbody></table></section>
                """.formatted(rows));
    }

    private static String actions(String csrf, String orderId, String state, boolean validator) {
        String action = switch (state) {
            case "ORDER_RECEIVED" -> button(csrf, orderId, "register", "Registrar muestra");
            case "SPECIMEN_REGISTERED" -> button(csrf, orderId, "receive", "Confirmar recepción");
            case "SPECIMEN_RECEIVED" -> button(csrf, orderId, "process", "Iniciar procesamiento");
            case "PROCESSING", "DRAFT" -> "";
            default -> "<p class=\"muted\">La muestra ya avanzó.</p>";
        };
        if (!validator && ("VALIDATED".equals(state) || "PUBLISHED".equals(state))) {
            return action;
        }
        return action;
    }

    private static String resultActions(String csrf, String orderId, String state, boolean validator) {
        if ("PROCESSING".equals(state) || "DRAFT".equals(state)) {
            return """
                    <form method="post" action="/bench/orders/%s">
                      <input type="hidden" name="csrf" value="%s"><input type="hidden" name="action" value="draft">
                      <label>Valor <input name="value" inputmode="decimal" required></label>
                      <label>Unidad <input name="unit" value="g/dL" required></label>
                      <label>Observación operativa <input name="note" maxlength="240"></label>
                      <button class="btn btn-primary" type="submit">Guardar borrador</button>
                    </form>
                    """.formatted(esc(orderId), esc(csrf))
                    + (validator && "DRAFT".equals(state) ? button(csrf, orderId, "validate", "Validar") : "");
        }
        if ("VALIDATED".equals(state) && validator) {
            return button(csrf, orderId, "publish", "Publicar");
        }
        if ("PUBLISHED".equals(state) && validator) {
            return """
                    <form method="post" action="/bench/orders/%s">
                      <input type="hidden" name="csrf" value="%s"><input type="hidden" name="action" value="correct">
                      <label>Valor corregido <input name="value" inputmode="decimal" required></label>
                      <button class="btn btn-secondary" type="submit">Guardar corrección</button>
                    </form>
                    """.formatted(esc(orderId), esc(csrf));
        }
        if ("VALIDATED".equals(state)) {
            return "<p class=\"muted\">La publicación requiere el rol de validación.</p>";
        }
        return "";
    }

    private static String button(String csrf, String orderId, String action, String label) {
        return """
                <form method="post" action="/bench/orders/%s">
                  <input type="hidden" name="csrf" value="%s"><input type="hidden" name="action" value="%s">
                  <button class="btn btn-primary" type="submit">%s</button>
                </form>
                """.formatted(esc(orderId), esc(csrf), esc(action), esc(label));
    }

    private static boolean visible(String view, String state) {
        return switch (view) {
            case "samples" -> "ORDER_RECEIVED".equals(state) || "SPECIMEN_REGISTERED".equals(state) || "SPECIMEN_RECEIVED".equals(state);
            case "processing" -> "PROCESSING".equals(state);
            case "results" -> "DRAFT".equals(state) || "VALIDATED".equals(state) || "PUBLISHED".equals(state);
            case "validation" -> "DRAFT".equals(state) || "VALIDATED".equals(state);
            case "alerts" -> "PUBLISHED".equals(state);
            default -> true;
        };
    }

    private static String roleLabel(String role) {
        return switch (role) {
            case "lab-validator" -> "Validador";
            case "receptionist" -> "Recepción";
            case "auditor" -> "Auditor";
            default -> "Técnico";
        };
    }

    static String label(String state) {
        return switch (state) {
            case "ORDER_RECEIVED" -> "Orden recibida";
            case "SPECIMEN_REGISTERED" -> "Muestra registrada";
            case "SPECIMEN_RECEIVED" -> "Muestra recibida";
            case "PROCESSING" -> "En procesamiento";
            case "DRAFT" -> "Resultado en borrador";
            case "VALIDATED" -> "Resultado validado";
            case "PUBLISHED" -> "Resultado publicado";
            default -> state;
        };
    }

    private static String page(BenchController.BenchPrincipal principal, String csrf, String active, String notice, String title, String body) {
        String mode = "oidc".equals(principal.sessionMode()) ? "Sesión OIDC" : "Sesión local";
        String session = """
                <div class="session"><span>%s · %s · %s · %s</span>
                <form method="post" action="/bench/logout"><input type="hidden" name="csrf" value="%s">
                <button class="btn btn-secondary" type="submit">Cerrar sesión</button></form></div>
                """.formatted(esc(roleLabel(principal.role())), esc(principal.userId()),
                esc(principal.organizationId()), esc(mode), esc(csrf));
        return """
                <!DOCTYPE html>
                <html lang="es"><head>%s<title>%s</title></head><body>
                <a class="skip" href="#contenido">Saltar al contenido</a>
                <header class="topbar"><div class="topbar-inner"><a class="brand" href="/bench/orders"><span class="mark" aria-hidden="true"></span><span><strong>Healthcare Lab</strong><span>Mini LIS</span></span></a>%s</div></header>
                <nav class="nav" aria-label="Principal"><div class="nav-inner">%s</div></nav>
                <main class="page" id="contenido">%s<h1 class="episode-code">%s</h1>%s</main>
                </body></html>
                """.formatted(head(), esc(title), session, nav(active), alert(notice), esc(title), body);
    }

    private static String nav(String active) {
        return link("orders", "/bench/orders", "Órdenes", active)
                + link("samples", "/bench/orders?vista=muestras", "Muestras", active)
                + link("processing", "/bench/orders?vista=procesamiento", "Procesamiento", active)
                + link("results", "/bench/orders?vista=resultados", "Resultados", active)
                + link("validation", "/bench/orders?vista=validacion", "Validación", active)
                + link("alerts", "/bench/orders?vista=alertas", "Alertas", active)
                + link("audit", "/bench/audit", "Auditoría", active);
    }

    private static String link(String key, String href, String label, String active) {
        String current = key.equals(active) ? " aria-current=\"page\"" : "";
        return "<a href=\"" + href + "\"" + current + ">" + label + "</a>";
    }

    private static String head() {
        return """
                <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
                <link rel="stylesheet" href="/bench/app.css">
                """;
    }

    private static String alert(String code) {
        if (code == null || code.isBlank()) {
            return "";
        }
        String tone = switch (code) {
            case "transicion", "no-autorizado", "entrada", "sesion", "credenciales" -> "warning";
            default -> "ok";
        };
        return "<p class=\"notice\" data-tone=\"" + tone + "\">" + esc(message(code)) + "</p>";
    }

    static String message(String code) {
        return switch (code) {
            case "muestra-registrada" -> "La muestra quedó registrada.";
            case "muestra-recibida" -> "La recepción de la muestra quedó confirmada.";
            case "procesamiento" -> "La muestra quedó en procesamiento.";
            case "borrador" -> "El borrador quedó guardado. No se publicó el resultado.";
            case "validado" -> "El resultado quedó validado. Todavía no se publicó.";
            case "publicado" -> "El resultado quedó publicado. El conector envía el mensaje una sola vez.";
            case "corregido" -> "La corrección quedó registrada y el resultado anterior se conserva.";
            case "transicion" -> "Esa transición no está permitida.";
            case "no-autorizado" -> "Esta operación no está autorizada para su rol.";
            case "entrada" -> "El valor o la unidad no son válidos.";
            case "sesion" -> "La sesión no está activa.";
            case "credenciales" -> "Las credenciales no son válidas.";
            default -> "";
        };
    }

    private static String esc(String value) {
        if (value == null) {
            return "";
        }
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;");
    }
}
