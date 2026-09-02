package lab.healthcare.fhir.smart;

import lab.healthcare.fhir.auth.AccessToken;
import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;

/**
 * Outcome of an interactive token exchange. The token value is never printed.
 */
public record SmartTokenExchangeResult(AccessToken token, SmartTokenExchangeDiagnosis diagnosis) {

    public SmartTokenExchangeResult {
        if (diagnosis == null) {
            throw new IllegalArgumentException("token exchange diagnosis must be provided");
        }
    }

    public boolean succeeded() {
        return diagnosis.tokenIssued() && token != null;
    }

    public IssuedAccessTokenProvider asProvider() {
        if (!succeeded()) {
            throw new SmartAuthorizationException("SMART authorization failed: no issued access token");
        }
        return new IssuedAccessTokenProvider(token);
    }

    @Override
    public String toString() {
        return "SmartTokenExchangeResult[succeeded="
                + succeeded()
                + ", diagnosis="
                + diagnosis
                + "]";
    }
}
