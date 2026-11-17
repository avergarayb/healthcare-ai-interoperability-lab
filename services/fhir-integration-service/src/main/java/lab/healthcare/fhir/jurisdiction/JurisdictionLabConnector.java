package lab.healthcare.fhir.jurisdiction;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import lab.healthcare.fhir.clinicalread.ClinicalReadException;
import lab.healthcare.fhir.federation.ClinicalConnector;

import java.util.ArrayList;
import java.util.List;

/**
 * One explicit federation source for the server-selected demonstration profile.
 * The resources are synthetic and local. This connector does not call a national network.
 */
public final class JurisdictionLabConnector implements ClinicalConnector {

    private final JurisdictionProfile profile;
    private final ObjectMapper json = new ObjectMapper();

    public JurisdictionLabConnector(JurisdictionProfile profile) {
        if (profile == null) {
            throw new IllegalStateException("profile_unknown");
        }
        this.profile = profile;
    }

    @Override
    public String key() {
        return profile.sourceKey();
    }

    @Override
    public String resolvePatient(String identifierSystem, String identifierValue) {
        if (profile.patientSystem().equals(identifierSystem) && profile.patientValue().equals(identifierValue)) {
            return profile.logicalId();
        }
        return null;
    }

    @Override
    public Collected collect(String resourceType, String patientId) {
        if (!profile.logicalId().equals(patientId)) {
            throw ClinicalReadException.notFound();
        }
        List<ObjectNode> accepted = new ArrayList<>();
        for (ObjectNode resource : profile.resources(json)) {
            if (!resourceType.equals(resource.path("resourceType").asText())) {
                continue;
            }
            String outcome = JurisdictionLabValidator.validate(profile, resource);
            if (!"accepted".equals(outcome)) {
                throw ClinicalReadException.external("response_rejected");
            }
            ObjectNode copy = resource.deepCopy();
            JurisdictionLabValidator.stamp(profile, copy);
            accepted.add(copy);
        }
        if (accepted.isEmpty()) {
            throw ClinicalReadException.notFound();
        }
        return new Collected(List.copyOf(accepted), false);
    }
}
