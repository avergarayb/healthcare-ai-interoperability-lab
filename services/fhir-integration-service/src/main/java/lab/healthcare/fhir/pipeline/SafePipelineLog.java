package lab.healthcare.fhir.pipeline;

import java.util.Locale;
import java.util.StringJoiner;

/**
 * Structured pipeline log lines. Rejects credential-like text.
 */
public final class SafePipelineLog {

    private SafePipelineLog() {
    }

    public static String line(PipelineDiagnosis diagnosis, String destination) {
        StringJoiner joiner = new StringJoiner(" ");
        joiner.add("PIPELINE");
        add(joiner, "destination", destination == null ? "" : destination.trim());
        add(joiner, "overall", diagnosis.overall().name());
        add(joiner, "contractValid", Boolean.toString(diagnosis.contractValid()));
        add(joiner, "usable", Boolean.toString(diagnosis.usable()));
        for (PipelineStageDiagnosis stage : diagnosis.stages()) {
            add(joiner, stage.stage(), stage.status().name());
            if (stage.error() != null) {
                add(joiner, stage.stage() + "Code", stage.error().code());
                add(joiner, stage.stage() + "Retryable", Boolean.toString(stage.error().retryable()));
            }
            if (stage.receivedCount() != null) {
                add(joiner, stage.stage() + "Received", Integer.toString(stage.receivedCount()));
            }
            if (stage.retainedCount() != null) {
                add(joiner, stage.stage() + "Retained", Integer.toString(stage.retainedCount()));
            }
            if (stage.truncated() != null) {
                add(joiner, stage.stage() + "Truncated", Boolean.toString(stage.truncated()));
            }
        }
        return sanitize(joiner.toString());
    }

    public static String sanitize(String text) {
        if (text == null) {
            return "";
        }
        String lower = text.toLowerCase(Locale.ROOT);
        if (lower.contains("access_token")
                || lower.contains("client_secret")
                || lower.contains("refresh_token")
                || lower.contains("authorization_code")
                || lower.contains("code_verifier")
                || lower.contains("bearer ")) {
            throw new IllegalStateException("Pipeline log must not contain credentials");
        }
        return text;
    }

    private static void add(StringJoiner joiner, String key, String value) {
        if (value == null || value.isBlank()) {
            return;
        }
        joiner.add(key + "=" + value);
    }
}
