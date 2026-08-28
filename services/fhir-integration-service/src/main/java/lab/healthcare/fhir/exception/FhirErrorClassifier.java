package lab.healthcare.fhir.exception;

import lab.healthcare.fhir.auth.oauth2.OAuth2TokenException;

import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.server.exceptions.BaseServerResponseException;

import java.net.ConnectException;
import java.net.NoRouteToHostException;
import java.net.PortUnreachableException;
import java.net.SocketTimeoutException;
import java.net.UnknownHostException;
import java.net.http.HttpTimeoutException;
import java.nio.channels.UnresolvedAddressException;
import java.util.Locale;
import java.util.concurrent.TimeoutException;

/**
 * Maps HAPI/HTTP/OAuth/network failures to a bounded {@link FhirErrorCategory}.
 * Does not retry and does not log payloads.
 */
public final class FhirErrorClassifier {

    private FhirErrorClassifier() {
    }

    public static FhirErrorDetails classify(Throwable throwable) {
        if (throwable instanceof FhirClientException fhir) {
            return fhir.details();
        }
        if (find(throwable, OAuth2TokenException.class) != null) {
            return FhirErrorDetails.of(FhirErrorCategory.AUTHENTICATION_ERROR, null);
        }
        if (isTimeout(throwable)) {
            return FhirErrorDetails.of(FhirErrorCategory.TIMEOUT, null);
        }
        if (isConnectionFailure(throwable) || find(throwable, FhirClientConnectionException.class) != null) {
            // HAPI models client I/O as InternalErrorException (HTTP 500). That is not a FHIR server 500.
            return FhirErrorDetails.of(FhirErrorCategory.CONNECTION_ERROR, null);
        }
        BaseServerResponseException fhirResponse = find(throwable, BaseServerResponseException.class);
        if (fhirResponse != null) {
            return FhirErrorDetails.of(categoryForStatus(fhirResponse.getStatusCode()), fhirResponse.getStatusCode());
        }
        return FhirErrorDetails.of(FhirErrorCategory.UNKNOWN, null);
    }

    public static FhirErrorCategory categoryForStatus(int status) {
        if (status == 408) {
            return FhirErrorCategory.TIMEOUT;
        }
        if (status == 401) {
            return FhirErrorCategory.AUTHENTICATION_ERROR;
        }
        if (status == 403) {
            return FhirErrorCategory.AUTHORIZATION_ERROR;
        }
        if (status == 404 || status == 410) {
            return FhirErrorCategory.NOT_FOUND;
        }
        if (status == 409 || status == 412) {
            return FhirErrorCategory.CONFLICT;
        }
        if (status == 429 || status >= 500) {
            return FhirErrorCategory.SERVER_ERROR;
        }
        if (status >= 400) {
            return FhirErrorCategory.VALIDATION_ERROR;
        }
        return FhirErrorCategory.UNKNOWN;
    }

    private static boolean isTimeout(Throwable throwable) {
        for (Throwable current = throwable; current != null; current = current.getCause()) {
            if (current instanceof SocketTimeoutException
                    || current instanceof TimeoutException
                    || current instanceof HttpTimeoutException) {
                return true;
            }
            String className = current.getClass().getSimpleName();
            if (className.contains("Timeout")) {
                return true;
            }
            String message = current.getMessage();
            if (message != null) {
                String lower = message.toLowerCase(Locale.ROOT);
                if (lower.contains("timed out") || lower.contains("timeout")) {
                    return true;
                }
            }
        }
        return false;
    }

    private static boolean isConnectionFailure(Throwable throwable) {
        for (Throwable current = throwable; current != null; current = current.getCause()) {
            if (current instanceof ConnectException
                    || current instanceof UnknownHostException
                    || current instanceof NoRouteToHostException
                    || current instanceof PortUnreachableException
                    || current instanceof UnresolvedAddressException) {
                return true;
            }
        }
        return false;
    }

    private static <T extends Throwable> T find(Throwable throwable, Class<T> type) {
        for (Throwable current = throwable; current != null; current = current.getCause()) {
            if (type.isInstance(current)) {
                return type.cast(current);
            }
        }
        return null;
    }
}
