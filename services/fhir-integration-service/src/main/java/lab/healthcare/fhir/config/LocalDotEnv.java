package lab.healthcare.fhir.config;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

/**
 * Loads a local {@code .env} into system properties for {@code mvn spring-boot:run}.
 * Tests do not call this. Values are never logged.
 */
public final class LocalDotEnv {

    private LocalDotEnv() {
    }

    public static boolean loadIfPresent() {
        Path file = locate();
        if (file == null) {
            return false;
        }
        try {
            List<String> lines = Files.readAllLines(file, StandardCharsets.UTF_8);
            for (String raw : lines) {
                apply(raw);
            }
            return true;
        } catch (Exception ex) {
            return false;
        }
    }

    static Path locate() {
        Path cwd = Path.of("").toAbsolutePath();
        List<Path> candidates = List.of(
                cwd.resolve(".env"),
                cwd.getParent() == null ? cwd.resolve(".env") : cwd.getParent().resolve(".env"),
                cwd.getParent() != null && cwd.getParent().getParent() != null
                        ? cwd.getParent().getParent().resolve(".env")
                        : cwd.resolve(".env"));
        for (Path candidate : candidates) {
            if (Files.isRegularFile(candidate)) {
                return candidate;
            }
        }
        return null;
    }

    static void apply(String raw) {
        if (raw == null) {
            return;
        }
        String line = raw.trim();
        if (line.isEmpty() || line.startsWith("#")) {
            return;
        }
        int separator = line.indexOf('=');
        if (separator <= 0) {
            return;
        }
        String key = line.substring(0, separator).trim();
        String value = unquote(line.substring(separator + 1).trim());
        if (key.isEmpty() || System.getenv(key) != null && !System.getenv(key).isBlank()) {
            return;
        }
        if (System.getProperty(key) != null && !System.getProperty(key).isBlank()) {
            return;
        }
        System.setProperty(key, value);
    }

    private static String unquote(String value) {
        if (value.length() >= 2
                && ((value.startsWith("\"") && value.endsWith("\""))
                        || (value.startsWith("'") && value.endsWith("'")))) {
            return value.substring(1, value.length() - 1);
        }
        return value;
    }
}
