package lab.healthcare.minihis;

import java.io.Serializable;

public record WardPrincipal(String userId, String role, String organizationId) implements Serializable {
}
