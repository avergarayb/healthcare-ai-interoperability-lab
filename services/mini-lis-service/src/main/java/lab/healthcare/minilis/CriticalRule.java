package lab.healthcare.minilis;

/**
 * Simulation rule sim-hemoglobin-low 1.0. LOINC 718-7 and g/dL are already used
 * by this laboratory. The catalog hemoglobin 13.4 g/dL does not match.
 * Keep the twin in Mini HIS aligned.
 */
public final class CriticalRule {

    public static final String ID = "sim-hemoglobin-low";
    public static final String VERSION = "1.0";
    public static final String TEST_CODE = "718-7";
    public static final String UNIT = "g/dL";
    public static final double THRESHOLD = 7.0;

    private CriticalRule() {
    }

    public static boolean matches(String testCode, String unit, String value) {
        if (!TEST_CODE.equals(testCode) || !UNIT.equals(unit) || value == null || !value.matches("[0-9]+(?:\\.[0-9]+)?")) {
            return false;
        }
        return Double.parseDouble(value) < THRESHOLD;
    }
}
