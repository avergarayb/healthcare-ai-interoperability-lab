package lab.healthcare.fhir.auth;

import ca.uhn.fhir.rest.client.api.IHttpRequest;
import org.junit.jupiter.api.Test;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

class BearerAccessTokenInterceptorTest {

    @Test
    void interceptRequestAddsBearerAuthorization() {
        IHttpRequest request = mock(IHttpRequest.class);
        BearerAccessTokenInterceptor interceptor = new BearerAccessTokenInterceptor(() -> "lab-access-token");

        interceptor.interceptRequest(request);

        verify(request).addHeader("Authorization", "Bearer lab-access-token");
    }

    @Test
    void interceptResponseDoesNotTouchTheRequest() {
        IHttpRequest request = mock(IHttpRequest.class);
        BearerAccessTokenInterceptor interceptor = new BearerAccessTokenInterceptor(() -> "lab-access-token");

        interceptor.interceptResponse(null);

        verifyNoInteractions(request);
    }
}
