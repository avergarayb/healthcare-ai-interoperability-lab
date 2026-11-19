package lab.healthcare.minihis;

import java.util.List;
import java.util.Map;

final class ShowcaseCatalog {

    private ShowcaseCatalog() {
    }

    record Step(String label, String href, boolean done, String evidence) {
    }

    record Card(String id, String name, String problem, String systems, String capabilities, String availability,
                String actionHref, String actionLabel) {
    }

    static String availability(String id, Map<String, Boolean> probes) {
        boolean lis = probes.getOrDefault("lis", false);
        boolean fhir = probes.getOrDefault("fhir", false);
        boolean ai = probes.getOrDefault("ai", false);
        boolean longitudinal = probes.getOrDefault("longitudinal", false);
        return switch (id) {
            case "demo-002" -> longitudinal ? "Disponible" : "Perfil aislado";
            case "demo-001" -> fhir && ai ? "Disponible" : "No disponible";
            case "demo-003" -> lis && fhir ? "Disponible" : "No disponible";
            case "demo-004" -> lis && fhir && ai ? "Disponible" : "No disponible";
            case "demo-005" -> ai ? "Disponible" : "No disponible";
            default -> "No disponible";
        };
    }

    static List<Card> cards(Map<String, Boolean> probes) {
        return List.of(
                card("demo-001", "Resumen de laboratorio",
                        "Ver en un expediente el resultado del hospital y el del laboratorio antes de que una persona acepte el texto.",
                        "Mini HIS, Mini LIS, federación, MCP, LangGraph y revisión humana.",
                        "El agente lab-result-summary-v1 resume. El modelo queda interceptado.",
                        probes, "/showcase/demo-001", "Abrir resumen"),
                card("demo-002", "Comparación longitudinal",
                        "Mostrar una diferencia entre dos fechas sin mezclar pacientes ni permisos de Perú y España.",
                        "Dos perfiles independientes, OIDC de ese perfil y el motor determinista.",
                        "LangGraph explica la diferencia ya calculada. No une las organizaciones.",
                        probes, "/showcase/demo-002", "Ver el perfil aislado"),
                card("demo-003", "Interoperabilidad HL7/FHIR",
                        "Correlacionar una orden hospitalaria con el resultado del laboratorio.",
                        "Mini HIS, intercambio HL7 v2.5.1 y Mini LIS.",
                        "Java proyecta la orden y el resultado. El mensaje bruto no entra en el modelo.",
                        probes, "/showcase/demo-003", "Abrir intercambio"),
                card("demo-004", "Resultado crítico",
                        "Una regla determinista marca la hemoglobina crítica y una persona aprueba la tarea.",
                        "Mini HIS, Mini LIS, HL7/FHIR, MCP, RAG y LangGraph.",
                        "La regla sim-hemoglobin-low 1.0 no consulta al modelo.",
                        probes, "/showcase/demo-004", "Abrir resultado crítico"),
                card("demo-005", "Preparación de alta",
                        "Preparar el egreso con el contexto del episodio sin cerrarlo desde el modelo.",
                        "Mini HIS y el coordinador de alta.",
                        "RAG cita protocolos. La aprobación humana no cierra el episodio.",
                        probes, "/showcase/demo-005", "Abrir preparación"));
    }

    private static Card card(String id, String name, String problem, String systems, String capabilities,
                             Map<String, Boolean> probes, String href, String action) {
        return new Card(id, name, problem, systems, capabilities, availability(id, probes), href, action);
    }
}
