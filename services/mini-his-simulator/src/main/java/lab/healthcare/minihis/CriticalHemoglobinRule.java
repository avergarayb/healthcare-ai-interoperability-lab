package lab.healthcare.minihis;

import com.fasterxml.jackson.databind.JsonNode;

/**
 * Simulation rule sim-hemoglobin-low 1.0. Twin of the Mini LIS rule.
 * LOINC 718-7 and g/dL are already mapped. Hemoglobin 13.4 g/dL does not match.
 */
public final class CriticalHemoglobinRule {

    public static final String ID = "sim-hemoglobin-low";
    public static final String VERSION = "1.0";
    public static final String TEST_CODE = "718-7";
    public static final String UNIT = "g/dL";
    public static final double THRESHOLD = 7.0;

    private CriticalHemoglobinRule() {
    }

    public static boolean matches(String testCode, String unit, String value) {
        if (!TEST_CODE.equals(testCode) || !UNIT.equals(unit) || value == null || !value.matches("[0-9]+(?:\\.[0-9]+)?")) {
            return false;
        }
        return Double.parseDouble(value) < THRESHOLD;
    }

    public static Reading read(JsonNode report, String testCode) {
        String value = "";
        String unit = "";
        if (report != null) {
            for (JsonNode node : report.path("observations")) {
                JsonNode quantity = quantity(node);
                String candidate = quantity.path("value").asText("");
                if (candidate.isBlank()) {
                    continue;
                }
                value = candidate;
                unit = quantity.path("unit").asText("");
            }
        }
        return new Reading(value, unit, matches(testCode, unit, value));
    }

    private static JsonNode quantity(JsonNode node) {
        JsonNode direct = node.path("valueQuantity");
        if (!direct.path("value").asText("").isBlank()) {
            return direct;
        }
        return node.path("resource").path("valueQuantity");
    }

    public record Reading(String value, String unit, boolean critical) {
    }
}
