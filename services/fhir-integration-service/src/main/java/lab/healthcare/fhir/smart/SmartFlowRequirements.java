package lab.healthcare.fhir.smart;

/**
 * What this platform needs from SMART metadata for the current lab flow.
 * Additional grants and vendor capabilities stay out of this type.
 */
public record SmartFlowRequirements(
        boolean requireAuthorizationEndpoint,
        boolean requireTokenEndpoint,
        boolean requireAuthorizationCodeWhenDeclared,
        boolean requirePkceS256WhenDeclared) {

    public static SmartFlowRequirements authorizationCodePkceS256() {
        return new SmartFlowRequirements(true, true, true, true);
    }
}
