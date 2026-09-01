package lab.healthcare.fhir.capability;

import java.util.Locale;
import java.util.Optional;

/**
 * CapabilityStatement interaction codes this lab interprets. Not every FHIR
 * interaction, and not a claim that {@code FhirService} implements the write.
 */
public enum FhirInteraction {
    READ("read"),
    SEARCH_TYPE("search-type"),
    CREATE("create"),
    UPDATE("update"),
    DELETE("delete");

    private final String code;

    FhirInteraction(String code) {
        this.code = code;
    }

    public String code() {
        return code;
    }

    /**
     * Maps a FHIR interaction code. Unknown values such as {@code vread} are
     * omitted rather than invented.
     */
    public static Optional<FhirInteraction> fromCode(String value) {
        if (value == null || value.isBlank()) {
            return Optional.empty();
        }
        String normalized = value.trim().toLowerCase(Locale.ROOT);
        for (FhirInteraction interaction : values()) {
            if (interaction.code.equals(normalized)) {
                return Optional.of(interaction);
            }
        }
        return Optional.empty();
    }
}
