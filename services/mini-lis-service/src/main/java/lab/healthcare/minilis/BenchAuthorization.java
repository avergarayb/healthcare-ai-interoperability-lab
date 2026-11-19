package lab.healthcare.minilis;

import java.util.Set;

final class BenchAuthorization {
    private BenchAuthorization() {
    }

    static boolean permits(String role, String organization, String action) {
        if (!"org-mini-his".equals(organization) || action == null) {
            return false;
        }
        return switch (role) {
            case "receptionist" -> action.equals("register") || action.equals("receive");
            case "lab-technician" -> Set.of("register", "receive", "process", "draft").contains(action);
            case "lab-validator" -> Set.of("register", "receive", "process", "draft", "validate", "publish", "correct").contains(action);
            default -> false;
        };
    }
}
