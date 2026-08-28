package lab.healthcare.fhir.routing;

import lab.healthcare.fhir.auth.AccessTokenProvider;
import lab.healthcare.fhir.client.FhirAccessTokenProviders;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.client.FhirService;
import lab.healthcare.fhir.server.FhirServerProfile;
import lab.healthcare.fhir.server.FhirServerProfileRegistry;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.Patient;
import org.springframework.stereotype.Service;

@Service
public class RoutingService {

    private final FhirServerProfileRegistry registry;
    private final FhirClientFactory clientFactory;
    private final FhirAccessTokenProviders tokenProviders;

    public RoutingService(
            FhirServerProfileRegistry registry,
            FhirClientFactory clientFactory,
            FhirAccessTokenProviders tokenProviders) {
        if (registry == null) {
            throw new IllegalArgumentException("FHIR server profile registry must be provided");
        }
        if (clientFactory == null) {
            throw new IllegalArgumentException("FHIR client factory must be provided");
        }
        if (tokenProviders == null) {
            throw new IllegalArgumentException("Access token providers must be provided");
        }
        this.registry = registry;
        this.clientFactory = clientFactory;
        this.tokenProviders = tokenProviders;
    }

    public FhirServerProfile resolve(RoutingRequest request) {
        requireRequest(request);
        try {
            return registry.enabledProfile(request.destination());
        } catch (IllegalStateException | IllegalArgumentException ex) {
            throw new RoutingException(ex.getMessage(), ex);
        }
    }

    public IGenericClient client(RoutingRequest request) {
        FhirServerProfile profile = resolve(request);
        AccessTokenProvider tokenProvider = tokenProviders.forProfile(profile);
        FhirContext fhirContext = clientFactory.createContext(profile);
        return clientFactory.createClient(fhirContext, profile, tokenProvider);
    }

    public Patient readPatient(RoutingRequest request) {
        FhirServerProfile profile = resolve(request);
        if (!(request.resource() instanceof Patient patient)) {
            throw new RoutingException(
                    "Routing request resource must be a Patient for destination '" + profile.name() + "'");
        }
        String logicalId = patient.getIdElement().getIdPart();
        if (logicalId == null || logicalId.isBlank()) {
            throw new RoutingException("Patient logical ID must be provided");
        }
        return new FhirService(client(request)).readPatient(logicalId);
    }

    private static void requireRequest(RoutingRequest request) {
        if (request == null) {
            throw new IllegalArgumentException("Routing request must be provided");
        }
    }
}
