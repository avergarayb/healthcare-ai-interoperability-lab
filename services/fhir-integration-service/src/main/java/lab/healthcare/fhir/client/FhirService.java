package lab.healthcare.fhir.client;

import ca.uhn.fhir.model.api.IQueryParameterType;
import ca.uhn.fhir.rest.api.MethodOutcome;
import ca.uhn.fhir.rest.client.api.IGenericClient;
import ca.uhn.fhir.rest.client.exceptions.FhirClientConnectionException;
import ca.uhn.fhir.rest.param.HasParam;
import ca.uhn.fhir.rest.server.exceptions.BaseServerResponseException;
import org.hl7.fhir.instance.model.api.IBaseOperationOutcome;
import org.hl7.fhir.instance.model.api.IIdType;
import org.hl7.fhir.r4.model.BooleanType;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.CanonicalType;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.CodeType;
import org.hl7.fhir.r4.model.CodeableConcept;
import org.hl7.fhir.r4.model.CodeSystem;
import org.hl7.fhir.r4.model.Coding;
import org.hl7.fhir.r4.model.Condition;
import org.hl7.fhir.r4.model.IdType;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.OperationOutcome;
import org.hl7.fhir.r4.model.Parameters;
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Reference;
import org.hl7.fhir.r4.model.Resource;
import org.hl7.fhir.r4.model.UriType;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.function.Supplier;

@Service
public class FhirService {

    static final int MAX_SEARCH_PAGES = 20;

    private final IGenericClient fhirClient;

    public FhirService(IGenericClient fhirClient) {
        this.fhirClient = fhirClient;
    }

    public CapabilityStatement retrieveCapabilityStatement() {
        return execute(
                () -> fhirClient.capabilities()
                        .ofType(CapabilityStatement.class)
                        .execute(),
                "retrieving metadata");
    }

    public Patient readPatient(String logicalId) {
        requireText(logicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.read()
                        .resource(Patient.class)
                        .withId(logicalId)
                        .execute(),
                "reading Patient/" + logicalId);
    }

    public Bundle searchPatientsByName(String name) {
        requireText(name, "Patient name search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.NAME.matches().value(name))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient by name");
    }

    public Bundle searchPatientsByIdentifier(String identifier) {
        requireText(identifier, "Patient identifier search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.IDENTIFIER.exactly().identifier(identifier))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient by identifier");
    }

    public List<Patient> extractPatients(Bundle bundle) {
        return extractResources(bundle, Patient.class);
    }

    public Observation readObservation(String logicalId) {
        requireText(logicalId, "Observation logical ID must be provided");
        return execute(
                () -> fhirClient.read()
                        .resource(Observation.class)
                        .withId(logicalId)
                        .execute(),
                "reading Observation/" + logicalId);
    }

    public Condition readCondition(String logicalId) {
        requireText(logicalId, "Condition logical ID must be provided");
        return execute(
                () -> fhirClient.read()
                        .resource(Condition.class)
                        .withId(logicalId)
                        .execute(),
                "reading Condition/" + logicalId);
    }

    public Bundle searchObservationsByPatient(String patientLogicalId) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Observation.class)
                        .where(Observation.PATIENT.hasId(patientLogicalId))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Observation by patient");
    }

    public Bundle searchConditionsByPatient(String patientLogicalId) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Condition.class)
                        .where(Condition.PATIENT.hasId(patientLogicalId))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Condition by patient");
    }

    public List<Observation> extractObservations(Bundle bundle) {
        return extractResources(bundle, Observation.class);
    }

    public List<Condition> extractConditions(Bundle bundle) {
        return extractResources(bundle, Condition.class);
    }

    public Bundle searchPatientsByNameAndGender(String name, String gender) {
        requireText(name, "Patient name search parameter must be provided");
        requireText(gender, "Patient gender search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.NAME.matches().value(name))
                        .and(Patient.GENDER.exactly().code(gender))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient by name and gender");
    }

    public Bundle searchPatientsByNameExact(String name) {
        requireText(name, "Patient name search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.NAME.matchesExactly().value(name))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient by name:exact");
    }

    public Bundle searchPatientsBornOnOrAfter(String birthDate) {
        requireText(birthDate, "Patient birthdate search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.BIRTHDATE.afterOrEquals().day(birthDate))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient by birthdate=ge" + birthDate);
    }

    public Bundle searchPatientsBornBefore(String birthDate) {
        requireText(birthDate, "Patient birthdate search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.BIRTHDATE.before().day(birthDate))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient by birthdate=lt" + birthDate);
    }

    public Bundle searchPatientsSortedByBirthDateAscending() {
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .sort()
                        .ascending(Patient.BIRTHDATE)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _sort=birthdate");
    }

    public Bundle searchPatientsSortedByBirthDateDescending() {
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .sort()
                        .descending(Patient.BIRTHDATE)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _sort=-birthdate");
    }

    public Bundle searchPatientsWithCount(int pageSize) {
        if (pageSize < 1) {
            throw new IllegalArgumentException("Patient _count must be at least 1");
        }
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .count(pageSize)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _count=" + pageSize);
    }

    public Bundle searchPatientsByFamilyWithCount(String family, int pageSize) {
        requireText(family, "Patient family search parameter must be provided");
        if (pageSize < 1) {
            throw new IllegalArgumentException("Patient _count must be at least 1");
        }
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.FAMILY.matches().value(family))
                        .count(pageSize)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient by family with _count=" + pageSize);
    }

    public Bundle searchPatientsByNameWithCount(String name, int pageSize) {
        requireText(name, "Patient name search parameter must be provided");
        if (pageSize < 1) {
            throw new IllegalArgumentException("Patient _count must be at least 1");
        }
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.NAME.matches().value(name))
                        .count(pageSize)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient by name with _count=" + pageSize);
    }

    public boolean hasNextPage(Bundle bundle) {
        requireResource(bundle, "Bundle must be provided");
        return hasLink(bundle, Bundle.LINK_NEXT);
    }

    public boolean hasLink(Bundle bundle, String relation) {
        requireResource(bundle, "Bundle must be provided");
        requireText(relation, "Bundle link relation must be provided");
        Bundle.BundleLinkComponent link = bundle.getLink(relation);
        return link != null && link.hasUrl();
    }

    public String bundleLink(Bundle bundle, String relation) {
        requireResource(bundle, "Bundle must be provided");
        requireText(relation, "Bundle link relation must be provided");
        if (!hasLink(bundle, relation)) {
            throw new IllegalArgumentException("Bundle has no " + relation + " link");
        }
        return bundle.getLink(relation).getUrl();
    }

    public Bundle nextPage(Bundle bundle) {
        requireResource(bundle, "Bundle must be provided");
        if (!hasNextPage(bundle)) {
            throw new IllegalArgumentException("Bundle has no next page link");
        }
        return execute(
                () -> fhirClient.loadPage()
                        .next(bundle)
                        .execute(),
                "loading next Bundle page");
    }

    public List<Bundle> fetchAllPages(Bundle firstPage) {
        requireResource(firstPage, "Bundle must be provided");
        List<Bundle> pages = new ArrayList<>();
        Set<String> seenNextUrls = new HashSet<>();
        Bundle current = firstPage;
        while (true) {
            pages.add(current);
            if (!hasNextPage(current)) {
                return pages;
            }
            String nextUrl = bundleLink(current, Bundle.LINK_NEXT);
            if (!seenNextUrls.add(nextUrl)) {
                throw new IllegalStateException("Search pagination repeated a next URL");
            }
            if (pages.size() >= MAX_SEARCH_PAGES) {
                throw new IllegalStateException("Search pagination exceeded " + MAX_SEARCH_PAGES + " pages");
            }
            current = nextPage(current);
        }
    }

    public Bundle searchObservationsByPatientAndCode(String patientLogicalId, String code) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        requireText(code, "Observation code search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Observation.class)
                        .where(Observation.PATIENT.hasId(patientLogicalId))
                        .and(Observation.CODE.exactly().code(code))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Observation by patient and code");
    }

    public Bundle searchObservationsByPatientAndCodeSortedByDate(
            String patientLogicalId,
            String code,
            int pageSize) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        requireText(code, "Observation code search parameter must be provided");
        if (pageSize < 1) {
            throw new IllegalArgumentException("Observation _count must be at least 1");
        }
        return execute(
                () -> fhirClient.search()
                        .forResource(Observation.class)
                        .where(Observation.PATIENT.hasId(patientLogicalId))
                        .and(Observation.CODE.exactly().code(code))
                        .sort()
                        .descending(Observation.DATE)
                        .count(pageSize)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Observation by patient, code, _sort=-date, and _count");
    }

    public Bundle searchConditionsByPatientAndClinicalStatus(String patientLogicalId, String clinicalStatus) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        requireText(clinicalStatus, "Condition clinical-status search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Condition.class)
                        .where(Condition.PATIENT.hasId(patientLogicalId))
                        .and(Condition.CLINICAL_STATUS.exactly().code(clinicalStatus))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Condition by patient and clinical-status");
    }

    public Bundle searchObservationsByPatientName(String patientName) {
        requireText(patientName, "Patient name search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Observation.class)
                        .where(Observation.PATIENT.hasChainedProperty(Patient.NAME.matches().value(patientName)))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Observation by patient.name");
    }

    public Bundle searchObservationsByPatientNameAndCode(String patientName, String code) {
        requireText(patientName, "Patient name search parameter must be provided");
        requireText(code, "Observation code search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Observation.class)
                        .where(Observation.PATIENT.hasChainedProperty(Patient.NAME.matches().value(patientName)))
                        .and(Observation.CODE.exactly().code(code))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Observation by patient.name and code");
    }

    public Bundle searchObservationsByPatientIdentifier(String identifier) {
        requireText(identifier, "Patient identifier search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Observation.class)
                        .where(Observation.PATIENT.hasChainedProperty(
                                Patient.IDENTIFIER.exactly().identifier(identifier)))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Observation by patient.identifier");
    }

    public Bundle searchConditionsByPatientNameAndClinicalStatus(String patientName, String clinicalStatus) {
        requireText(patientName, "Patient name search parameter must be provided");
        requireText(clinicalStatus, "Condition clinical-status search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Condition.class)
                        .where(Condition.PATIENT.hasChainedProperty(Patient.NAME.matches().value(patientName)))
                        .and(Condition.CLINICAL_STATUS.exactly().code(clinicalStatus))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Condition by patient.name and clinical-status");
    }

    public Bundle searchPatientsHavingObservationCode(String code) {
        requireText(code, "Observation code search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(reverseChain("Observation", "patient", "code", code))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _has:Observation:patient:code");
    }

    public Bundle searchPatientsHavingConditionClinicalStatus(String clinicalStatus) {
        requireText(clinicalStatus, "Condition clinical-status search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(reverseChain("Condition", "patient", "clinical-status", clinicalStatus))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _has:Condition:patient:clinical-status");
    }

    public Bundle searchPatientsHavingObservationCodeAndGender(String code, String gender) {
        requireText(code, "Observation code search parameter must be provided");
        requireText(gender, "Patient gender search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(reverseChain("Observation", "patient", "code", code))
                        .and(Patient.GENDER.exactly().code(gender))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _has Observation code and gender");
    }

    public Bundle searchObservationsByCode(String code) {
        requireText(code, "Observation code search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Observation.class)
                        .where(Observation.CODE.exactly().code(code))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Observation by code");
    }

    public Bundle searchConditionsByCode(String code) {
        requireText(code, "Condition code search parameter must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Condition.class)
                        .where(Condition.CODE.exactly().code(code))
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Condition by code");
    }

    public Parameters validateCode(String system, String code) {
        requireText(system, "CodeSystem url must be provided");
        requireText(code, "Code must be provided");
        return execute(
                () -> fhirClient.operation()
                        .onType(CodeSystem.class)
                        .named("$validate-code")
                        .withParameter(Parameters.class, "url", new UriType(system))
                        .andParameter("code", new CodeType(code))
                        .useHttpGet()
                        .execute(),
                "validating code " + system + "#" + code);
    }

    public Boolean validationResult(Parameters parameters) {
        requireResource(parameters, "Parameters must be provided");
        Parameters.ParametersParameterComponent result = parameters.getParameter("result");
        if (result == null || !(result.getValue() instanceof BooleanType booleanType)) {
            throw new IllegalArgumentException("Parameters must contain a boolean result");
        }
        return booleanType.booleanValue();
    }

    public String validationMessage(Parameters parameters) {
        requireResource(parameters, "Parameters must be provided");
        Parameters.ParametersParameterComponent message = parameters.getParameter("message");
        if (message == null || !message.hasValue()) {
            return null;
        }
        return message.getValue().primitiveValue();
    }

    public Coding primaryCoding(CodeableConcept concept) {
        if (concept == null || !concept.hasCoding()) {
            throw new IllegalArgumentException("CodeableConcept coding must be provided");
        }
        return concept.getCodingFirstRep();
    }

    public MethodOutcome validateResource(Resource resource) {
        requireResource(resource, "Resource must be provided");
        Resource payload = typeLevelValidationCopy(resource);
        return execute(
                () -> fhirClient.validate()
                        .resource(payload)
                        .execute(),
                "validating " + resource.getResourceType().name());
    }

    public MethodOutcome validateResourceAgainstProfile(Resource resource, String profileUrl) {
        requireResource(resource, "Resource must be provided");
        requireText(profileUrl, "Profile URL must be provided");
        Resource payload = typeLevelValidationCopy(resource);
        if (declaredProfiles(payload).stream().noneMatch(profileUrl::equals)) {
            payload.getMeta().addProfile(profileUrl);
        }
        return execute(
                () -> fhirClient.validate()
                        .resource(payload)
                        .execute(),
                "validating " + resource.getResourceType().name() + " against profile " + profileUrl);
    }

    public OperationOutcome operationOutcome(MethodOutcome outcome) {
        if (outcome == null) {
            throw new IllegalArgumentException("MethodOutcome must be provided");
        }
        IBaseOperationOutcome base = outcome.getOperationOutcome();
        if (!(base instanceof OperationOutcome operationOutcome)) {
            throw new IllegalArgumentException("MethodOutcome must contain an OperationOutcome");
        }
        return operationOutcome;
    }

    public boolean hasErrorIssue(OperationOutcome outcome) {
        requireResource(outcome, "OperationOutcome must be provided");
        return outcome.getIssue().stream().anyMatch(issue ->
                issue.getSeverity() == OperationOutcome.IssueSeverity.ERROR
                        || issue.getSeverity() == OperationOutcome.IssueSeverity.FATAL);
    }

    public List<String> issueDiagnostics(OperationOutcome outcome) {
        requireResource(outcome, "OperationOutcome must be provided");
        return outcome.getIssue().stream()
                .map(OperationOutcome.OperationOutcomeIssueComponent::getDiagnostics)
                .filter(diagnostics -> diagnostics != null && !diagnostics.isBlank())
                .toList();
    }

    public List<String> declaredProfiles(Resource resource) {
        requireResource(resource, "Resource must be provided");
        return resource.getMeta().getProfile().stream()
                .map(CanonicalType::getValue)
                .filter(profile -> profile != null && !profile.isBlank())
                .toList();
    }

    public Bundle searchObservationsByPatientIncludingSubject(String patientLogicalId) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Observation.class)
                        .where(Observation.PATIENT.hasId(patientLogicalId))
                        .include(Observation.INCLUDE_SUBJECT)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Observation by patient with _include=Observation:subject");
    }

    public Bundle searchPatientRevincludingObservationSubject(String patientLogicalId) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.RES_ID.exactly().code(patientLogicalId))
                        .revInclude(Observation.INCLUDE_SUBJECT)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _revinclude=Observation:subject");
    }

    public Bundle searchPatientRevincludingConditionSubject(String patientLogicalId) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.RES_ID.exactly().code(patientLogicalId))
                        .revInclude(Condition.INCLUDE_SUBJECT)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _revinclude=Condition:subject");
    }

    public Bundle searchPatientRevincludingObservationAndConditionSubject(String patientLogicalId) {
        requireText(patientLogicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.search()
                        .forResource(Patient.class)
                        .where(Patient.RES_ID.exactly().code(patientLogicalId))
                        .revInclude(Observation.INCLUDE_SUBJECT)
                        .revInclude(Condition.INCLUDE_SUBJECT)
                        .returnBundle(Bundle.class)
                        .execute(),
                "searching Patient with _revinclude Observation:subject and Condition:subject");
    }

    public MethodOutcome createPatient(Patient patient) {
        requireResource(patient, "Patient must be provided");
        return execute(
                () -> fhirClient.create()
                        .resource(patient)
                        .execute(),
                "creating Patient");
    }

    public MethodOutcome updatePatient(Patient patient) {
        requireResource(patient, "Patient must be provided");
        String logicalId = requireLogicalId(patient, "Patient logical ID must be provided for update");
        return execute(
                () -> fhirClient.update()
                        .resource(patient)
                        .execute(),
                "updating Patient/" + logicalId);
    }

    public MethodOutcome deletePatient(String logicalId) {
        requireText(logicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.delete()
                        .resourceById("Patient", logicalId)
                        .execute(),
                "deleting Patient/" + logicalId);
    }

    public Bundle getPatientHistory(String logicalId) {
        requireText(logicalId, "Patient logical ID must be provided");
        return execute(
                () -> fhirClient.history()
                        .onInstance(new IdType("Patient", logicalId))
                        .returnBundle(Bundle.class)
                        .execute(),
                "retrieving Patient/" + logicalId + " history");
    }

    public Bundle getPatientHistory(String logicalId, int pageSize) {
        requireText(logicalId, "Patient logical ID must be provided");
        if (pageSize < 1) {
            throw new IllegalArgumentException("Patient history _count must be at least 1");
        }
        return execute(
                () -> fhirClient.history()
                        .onInstance(new IdType("Patient", logicalId))
                        .returnBundle(Bundle.class)
                        .count(pageSize)
                        .execute(),
                "retrieving Patient/" + logicalId + " history with _count=" + pageSize);
    }

    public Patient readPatientVersion(String logicalId, String versionId) {
        requireText(logicalId, "Patient logical ID must be provided");
        requireText(versionId, "Patient version ID must be provided");
        return execute(
                () -> fhirClient.read()
                        .resource(Patient.class)
                        .withIdAndVersion(logicalId, versionId)
                        .execute(),
                "reading Patient/" + logicalId + "/_history/" + versionId);
    }

    public String patientVersionId(Patient patient) {
        requireResource(patient, "Patient must be provided");
        if (!patient.hasMeta() || !patient.getMeta().hasVersionId()) {
            throw new IllegalArgumentException("Patient meta.versionId must be provided");
        }
        return patient.getMeta().getVersionId();
    }

    public MethodOutcome updatePatientIfMatch(Patient patient, String versionId) {
        requireResource(patient, "Patient must be provided");
        String logicalId = requireLogicalId(patient, "Patient logical ID must be provided for update");
        requireText(versionId, "Patient version ID must be provided");
        Patient toUpdate = patient.copy();
        toUpdate.setId(new IdType("Patient", logicalId, versionId));
        return execute(
                () -> fhirClient.update()
                        .resource(toUpdate)
                        .withAdditionalHeader("If-Match", "W/\"" + versionId + "\"")
                        .execute(),
                "updating Patient/" + logicalId + " with If-Match version " + versionId);
    }

    public List<String> historyVersionIds(Bundle bundle) {
        requireResource(bundle, "Bundle must be provided");
        return bundle.getEntry().stream()
                .map(FhirService::historyEntryVersionId)
                .toList();
    }

    public List<String> historyRequestMethods(Bundle bundle) {
        requireResource(bundle, "Bundle must be provided");
        return bundle.getEntry().stream()
                .map(entry -> entry.hasRequest() && entry.getRequest().hasMethod()
                        ? entry.getRequest().getMethod().toCode()
                        : null)
                .toList();
    }

    public List<String> historyResponseStatuses(Bundle bundle) {
        requireResource(bundle, "Bundle must be provided");
        return bundle.getEntry().stream()
                .map(entry -> entry.hasResponse() ? entry.getResponse().getStatus() : null)
                .toList();
    }

    public MethodOutcome createObservation(Observation observation) {
        requireResource(observation, "Observation must be provided");
        return execute(
                () -> fhirClient.create()
                        .resource(observation)
                        .execute(),
                "creating Observation");
    }

    public MethodOutcome deleteObservation(String logicalId) {
        requireText(logicalId, "Observation logical ID must be provided");
        return execute(
                () -> fhirClient.delete()
                        .resourceById("Observation", logicalId)
                        .execute(),
                "deleting Observation/" + logicalId);
    }

    public Bundle executeTransaction(Bundle bundle) {
        requireResource(bundle, "Bundle must be provided");
        if (bundle.getType() != Bundle.BundleType.TRANSACTION) {
            throw new IllegalArgumentException("Bundle type must be transaction");
        }
        return execute(
                () -> fhirClient.transaction()
                        .withBundle(bundle)
                        .execute(),
                "executing transaction Bundle");
    }

    public Bundle executeBatch(Bundle bundle) {
        requireResource(bundle, "Bundle must be provided");
        if (bundle.getType() != Bundle.BundleType.BATCH) {
            throw new IllegalArgumentException("Bundle type must be batch");
        }
        return execute(
                () -> fhirClient.transaction()
                        .withBundle(bundle)
                        .execute(),
                "executing batch Bundle");
    }

    public Bundle patientAndObservationCreateTransaction(Patient patient, Observation observation) {
        requireResource(patient, "Patient must be provided");
        requireResource(observation, "Observation must be provided");
        String patientFullUrl = "urn:uuid:" + UUID.randomUUID();
        Patient patientEntry = patient.copy();
        patientEntry.setIdElement(new IdType());
        Observation observationEntry = observation.copy();
        observationEntry.setIdElement(new IdType());
        observationEntry.setSubject(new Reference(patientFullUrl));

        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.TRANSACTION);
        addRequestEntry(bundle, patientFullUrl, patientEntry, Bundle.HTTPVerb.POST, "Patient", null);
        addRequestEntry(bundle, null, observationEntry, Bundle.HTTPVerb.POST, "Observation", null);
        return bundle;
    }

    public Bundle conditionalCreatePatientTransaction(Patient patient) {
        requireResource(patient, "Patient must be provided");
        if (!patient.hasIdentifier()
                || !patient.getIdentifierFirstRep().hasSystem()
                || !patient.getIdentifierFirstRep().hasValue()) {
            throw new IllegalArgumentException("Patient identifier system and value must be provided");
        }
        String ifNoneExist = "identifier="
                + patient.getIdentifierFirstRep().getSystem()
                + "|"
                + patient.getIdentifierFirstRep().getValue();
        Patient patientEntry = patient.copy();
        patientEntry.setIdElement(new IdType());
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.TRANSACTION);
        addRequestEntry(bundle, null, patientEntry, Bundle.HTTPVerb.POST, "Patient", ifNoneExist);
        return bundle;
    }

    public Bundle patientCreateAndGetBatch(Patient patient, String existingPatientLogicalId) {
        requireResource(patient, "Patient must be provided");
        requireText(existingPatientLogicalId, "Existing Patient logical ID must be provided");
        Patient patientEntry = patient.copy();
        patientEntry.setIdElement(new IdType());
        Bundle bundle = new Bundle();
        bundle.setType(Bundle.BundleType.BATCH);
        addRequestEntry(bundle, null, patientEntry, Bundle.HTTPVerb.POST, "Patient", null);
        bundle.addEntry().getRequest()
                .setMethod(Bundle.HTTPVerb.GET)
                .setUrl("Patient/this-patient-does-not-exist-batch");
        bundle.addEntry().getRequest()
                .setMethod(Bundle.HTTPVerb.GET)
                .setUrl("Patient/" + existingPatientLogicalId);
        return bundle;
    }

    public List<String> entryResponseStatuses(Bundle bundle) {
        requireResource(bundle, "Bundle must be provided");
        return bundle.getEntry().stream()
                .map(entry -> entry.hasResponse() ? entry.getResponse().getStatus() : null)
                .toList();
    }

    public String entryResponseLocation(Bundle bundle, int index) {
        requireResource(bundle, "Bundle must be provided");
        if (index < 0 || index >= bundle.getEntry().size()) {
            throw new IllegalArgumentException("Bundle entry index is out of range");
        }
        String location = bundle.getEntry().get(index).getResponse().getLocation();
        requireText(location, "Bundle entry response location must be provided");
        return location;
    }

    public String logicalIdFromLocation(String location) {
        requireText(location, "Response location must be provided");
        IdType id = new IdType(location);
        if (!id.hasIdPart()) {
            throw new IllegalArgumentException("Response location must contain a resource identity");
        }
        return id.getIdPart();
    }

    public String createdLogicalId(MethodOutcome outcome) {
        if (outcome == null) {
            throw new IllegalArgumentException("MethodOutcome must be provided");
        }
        IIdType id = outcome.getId();
        if (id == null || !id.hasIdPart()) {
            throw new IllegalArgumentException("MethodOutcome must contain a resource identity");
        }
        return id.getIdPart();
    }

    public List<String> resourceIdentities(Bundle bundle) {
        if (bundle == null) {
            throw new IllegalArgumentException("Bundle must be provided");
        }
        return bundle.getEntry().stream()
                .map(Bundle.BundleEntryComponent::getResource)
                .filter(Objects::nonNull)
                .map(resource -> resource.getResourceType().name() + "/" + resource.getIdElement().getIdPart())
                .toList();
    }

    public String subjectReference(Reference subject) {
        if (subject == null || !subject.hasReference()) {
            throw new IllegalArgumentException("Subject reference must be provided");
        }
        return subject.getReference();
    }

    private static String historyEntryVersionId(Bundle.BundleEntryComponent entry) {
        if (entry.hasResource()
                && entry.getResource().hasMeta()
                && entry.getResource().getMeta().hasVersionId()) {
            return entry.getResource().getMeta().getVersionId();
        }
        if (entry.hasRequest() && entry.getRequest().hasUrl()) {
            IdType requestId = new IdType(entry.getRequest().getUrl());
            if (requestId.hasVersionIdPart()) {
                return requestId.getVersionIdPart();
            }
        }
        throw new IllegalArgumentException("History entry has no version ID");
    }

    private static void addRequestEntry(
            Bundle bundle,
            String fullUrl,
            Resource resource,
            Bundle.HTTPVerb method,
            String url,
            String ifNoneExist) {
        Bundle.BundleEntryComponent entry = bundle.addEntry();
        if (fullUrl != null) {
            entry.setFullUrl(fullUrl);
        }
        entry.setResource(resource);
        entry.getRequest().setMethod(method).setUrl(url);
        if (ifNoneExist != null) {
            entry.getRequest().setIfNoneExist(ifNoneExist);
        }
    }

    private <T extends Resource> List<T> extractResources(Bundle bundle, Class<T> type) {
        if (bundle == null) {
            throw new IllegalArgumentException("Bundle must be provided");
        }
        return bundle.getEntry().stream()
                .map(Bundle.BundleEntryComponent::getResource)
                .filter(type::isInstance)
                .map(type::cast)
                .toList();
    }

    private <T> T execute(Supplier<T> operation, String action) {
        try {
            return operation.get();
        } catch (FhirClientConnectionException ex) {
            throw new FhirClientException("Unable to connect to the FHIR server while " + action, ex);
        } catch (BaseServerResponseException ex) {
            throw new FhirClientException("FHIR server returned an error while " + action, ex);
        }
    }

    private static Resource typeLevelValidationCopy(Resource resource) {
        Resource copy = resource.copy();
        copy.setIdElement(new IdType(copy.fhirType(), (String) null));
        return copy;
    }

    private static void requireText(String value, String message) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(message);
        }
    }

    private static void requireResource(Resource resource, String message) {
        if (resource == null) {
            throw new IllegalArgumentException(message);
        }
    }

    private static String requireLogicalId(Resource resource, String message) {
        String logicalId = resource.getIdElement().getIdPart();
        requireText(logicalId, message);
        return logicalId;
    }

    private static Map<String, List<IQueryParameterType>> reverseChain(
            String targetResourceType,
            String referenceSearchParam,
            String chainedSearchParam,
            String value) {
        return Map.of(
                "_has",
                List.of(new HasParam(targetResourceType, referenceSearchParam, chainedSearchParam, value)));
    }
}
