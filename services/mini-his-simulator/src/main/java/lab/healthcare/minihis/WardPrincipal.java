package lab.healthcare.minihis;

import java.io.Serializable;

public record WardPrincipal(String userId, String role, String organizationId, String sessionMode) implements Serializable {
    public WardPrincipal(String userId, String role, String organizationId) {
        this(userId, role, organizationId, "local");
    }
}
