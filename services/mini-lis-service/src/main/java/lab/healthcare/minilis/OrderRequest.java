package lab.healthcare.minilis;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.time.OffsetDateTime;

public record OrderRequest(
        @NotBlank @Pattern(regexp = "[A-Za-z0-9\\-.]{1,64}") String patientId,
        @NotBlank @Pattern(regexp = "[A-Za-z0-9\\-.]{1,64}") String requestingOrganizationId,
        @NotBlank @Pattern(regexp = "[A-Za-z0-9\\-.]{1,64}") String externalRequestId,
        @NotBlank @Pattern(regexp = "[A-Za-z0-9\\-.]{1,64}") String testCode,
        @NotBlank @Size(max = 200) String testDescription,
        @NotNull OffsetDateTime requestedAt) {
}
