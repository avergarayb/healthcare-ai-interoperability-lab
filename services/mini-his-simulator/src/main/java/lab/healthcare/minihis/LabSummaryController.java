package lab.healthcare.minihis;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Controller
@org.springframework.web.bind.annotation.ResponseBody
public class LabSummaryController {

    private static final String PATIENT = "MHS-PAT-001";

    private final MiniHisStore patients;
    private final LabOrderStore orders;
    private final LabSummaryClient summaries;
    private final String organizationId;
    private final boolean oidcEnabled;

    public LabSummaryController(
            MiniHisStore patients,
            LabOrderStore orders,
            LabSummaryClient summaries,
            @Value("${mini-his.organization-id}") String organizationId,
            @Value("${mini-his.oidc.enabled:false}") boolean oidcEnabled) {
        this.patients = patients;
        this.orders = orders;
        this.summaries = summaries;
        this.organizationId = organizationId;
        this.oidcEnabled = oidcEnabled;
    }

    @GetMapping(path = "/showcase/demo-001/case", produces = MediaType.TEXT_HTML_VALUE)
    public Object home(@RequestParam(name = "aviso", required = false) String notice, HttpServletRequest request) {
        if (principal(request) == null) {
            return redirect("/ward/login");
        }
        return ShowcaseView.summaryHome(patient(), localOrders(), clinician(request), csrf(request), safe(notice));
    }

    @PostMapping("/showcase/demo-001/case")
    public ResponseEntity<Void> prepare(HttpServletRequest request) {
        if (!clinician(request) || !csrfOk(request)) {
            return redirect("/ward/login?aviso=no-autorizado");
        }
        try {
            if (oidcEnabled && identityToken(request).isBlank()) {
                return redirect("/showcase/demo-001/case?aviso=unauthorized");
            }
            Map<String, Object> created = summaries.prepare(principal(request).userId(), identityToken(request));
            Object caseId = created.get("caseId");
            if (caseId instanceof String id && id.matches("sum-[0-9a-f]{12}")) {
                return redirect("/showcase/demo-001/case/" + id);
            }
            return redirect("/showcase/demo-001/case?aviso=summary_rejected");
        } catch (InpatientRejection ex) {
            return redirect("/showcase/demo-001/case?aviso=" + safe(ex.code()));
        }
    }

    @GetMapping(path = "/showcase/demo-001/case/{caseId:sum-[0-9a-f]{12}}", produces = MediaType.TEXT_HTML_VALUE)
    public Object show(@PathVariable String caseId, @RequestParam(name = "aviso", required = false) String notice,
                       HttpServletRequest request) {
        if (principal(request) == null) {
            return redirect("/ward/login");
        }
        try {
            return ShowcaseView.summaryResult(summaries.read(caseId), reviewer(request), csrf(request), safe(notice));
        } catch (InpatientRejection ex) {
            return redirect("/showcase/demo-001/case?aviso=" + safe(ex.code()));
        }
    }

    @PostMapping("/showcase/demo-001/case/{caseId:sum-[0-9a-f]{12}}/decision")
    public ResponseEntity<Void> decide(@PathVariable String caseId, @RequestParam String decision, HttpServletRequest request) {
        if (!reviewer(request) || !csrfOk(request)) {
            return redirect("/ward/login?aviso=no-autorizado");
        }
        if (!"approved".equals(decision) && !"rejected".equals(decision)) {
            return redirect("/showcase/demo-001/case/" + caseId + "?aviso=summary_rejected");
        }
        if (oidcEnabled && identityToken(request).isBlank()) {
            return redirect("/showcase/demo-001/case/" + caseId + "?aviso=unauthorized");
        }
        try {
            summaries.decide(caseId, decision, principal(request).userId(), identityToken(request));
            return redirect("/showcase/demo-001/case/" + caseId);
        } catch (InpatientRejection ex) {
            return redirect("/showcase/demo-001/case/" + caseId + "?aviso=" + safe(ex.code()));
        }
    }

    @PostMapping("/showcase/demo-001/case/{caseId:sum-[0-9a-f]{12}}/replay")
    public ResponseEntity<Void> replay(@PathVariable String caseId, HttpServletRequest request) {
        if (!clinician(request) || !csrfOk(request)) {
            return redirect("/ward/login?aviso=no-autorizado");
        }
        try {
            summaries.replay(caseId, principal(request).userId(), identityToken(request));
            return redirect("/showcase/demo-001/case/" + caseId + "?aviso=summary_rejected");
        } catch (InpatientRejection ex) {
            return redirect("/showcase/demo-001/case/" + caseId + "?aviso=" + safe(ex.code()));
        }
    }

    private PatientView patient() {
        return patients.findPatient(PATIENT).orElseThrow(() -> new InpatientRejection("not_found", 404));
    }

    private List<LabOrderView> localOrders() {
        List<LabOrderView> matched = new ArrayList<>();
        for (LabOrderView order : orders.listAll()) {
            if (PATIENT.equals(order.patientId())) {
                matched.add(order);
            }
            if (matched.size() == 6) {
                break;
            }
        }
        return matched;
    }

    private WardPrincipal principal(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        Object value = session == null ? null : session.getAttribute("wardPrincipal");
        if (value instanceof WardPrincipal principal && organizationId.equals(principal.organizationId())) {
            return principal;
        }
        return null;
    }

    private boolean clinician(HttpServletRequest request) {
        WardPrincipal principal = principal(request);
        return principal != null && "clinician".equals(principal.role());
    }

    private boolean reviewer(HttpServletRequest request) {
        WardPrincipal principal = principal(request);
        if (principal == null) {
            return false;
        }
        return oidcEnabled ? "clinical-reviewer".equals(principal.role()) : "clinician".equals(principal.role());
    }

    private static String identityToken(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        Object value = session == null ? null : session.getAttribute("hospitalAccessToken");
        return value instanceof String token && token.chars().filter(ch -> ch == '.').count() == 2 ? token : "";
    }

    private static String csrf(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        Object value = session == null ? null : session.getAttribute("csrf");
        return value instanceof String token ? token : "";
    }

    private static boolean csrfOk(HttpServletRequest request) {
        String expected = csrf(request);
        String presented = request.getParameter("csrf");
        return !expected.isBlank() && presented != null
                && MessageDigest.isEqual(expected.getBytes(StandardCharsets.UTF_8), presented.getBytes(StandardCharsets.UTF_8));
    }

    private static String safe(String code) {
        return code != null && code.matches("[a-z_]{1,40}") ? code : "";
    }

    private static ResponseEntity<Void> redirect(String location) {
        return ResponseEntity.status(303).location(URI.create(location)).build();
    }
}
