package lab.healthcare.fhir.client;

import ca.uhn.fhir.rest.client.api.IClientInterceptor;
import ca.uhn.fhir.rest.client.api.IHttpRequest;
import ca.uhn.fhir.rest.client.api.IHttpResponse;

public class BearerAccessTokenInterceptor implements IClientInterceptor {

    private final AccessTokenProvider tokenProvider;

    public BearerAccessTokenInterceptor(AccessTokenProvider tokenProvider) {
        if (tokenProvider == null) {
            throw new IllegalArgumentException("Access token provider must be provided");
        }
        this.tokenProvider = tokenProvider;
    }

    @Override
    public void interceptRequest(IHttpRequest theRequest) {
        theRequest.addHeader("Authorization", "Bearer " + tokenProvider.accessToken());
    }

    @Override
    public void interceptResponse(IHttpResponse theResponse) {
        // Bearer injection happens on the request. The FHIR server response is left unchanged.
    }
}
