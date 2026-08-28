package lab.healthcare.fhir.mapping;

public record FieldMapping(
        String source,
        String target,
        MappingConversion conversion,
        String constant) {

    public FieldMapping {
        if (target == null || target.isBlank()) {
            throw new IllegalArgumentException("Field mapping target must be provided");
        }
        conversion = conversion == null ? MappingConversion.STRING : conversion;
        boolean hasSource = source != null && !source.isBlank();
        boolean hasConstant = constant != null;
        if (hasSource == hasConstant) {
            throw new IllegalArgumentException("Field mapping must have either a source or a constant");
        }
        if (hasSource) {
            source = source.trim();
        }
        target = target.trim();
    }

    public static FieldMapping from(String source, String target) {
        return from(source, target, MappingConversion.STRING);
    }

    public static FieldMapping from(String source, String target, MappingConversion conversion) {
        return new FieldMapping(source, target, conversion, null);
    }

    public static FieldMapping constant(String target, String value) {
        return new FieldMapping(null, target, MappingConversion.STRING, value);
    }

    public boolean isConstant() {
        return constant != null;
    }
}
