package lab.healthcare.minilis;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.time.OffsetDateTime;

public record ResultRequest(
        @NotBlank @Pattern(regexp = "[A-Za-z0-9\\-.]{1,64}") String externalResultId,
        @NotBlank @Pattern(regexp = "[A-Za-z0-9\\-.]{1,64}") String testCode,
        @NotBlank @Size(max = 80) String value,
        @Size(max = 40) String unit,
        @Size(max = 80) String referenceRange,
        @NotNull OffsetDateTime resultedAt,
        @NotNull ResultStatus status) {
}
