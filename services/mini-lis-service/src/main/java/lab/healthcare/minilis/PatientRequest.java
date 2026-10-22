package lab.healthcare.minilis;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.time.LocalDate;

public record PatientRequest(
        @NotBlank @Pattern(regexp = "[A-Za-z0-9\\-.]{1,64}") String organizationId,
        @NotBlank @Pattern(regexp = "[A-Za-z0-9\\-.]{1,64}") String externalId,
        @NotBlank @Size(max = 80) String familyName,
        @NotBlank @Size(max = 80) String givenName,
        @NotNull LocalDate birthDate,
        @NotBlank @Pattern(regexp = "female|male|unknown") String administrativeSex) {
}
