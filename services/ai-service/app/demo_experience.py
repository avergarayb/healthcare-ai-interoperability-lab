"""Read-only explorer for stored cross-organization demonstration reports.

The page repeats the report. It does not evaluate the protocol again and it
does not read Clinical Read or HAPI.
"""

from __future__ import annotations

import json
import os
import re
from html import escape
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from app.followup_review import ReviewPersistenceUnavailable
from app.human_development_auth import require_human_session


EXECUTION_ID = re.compile(r"^E2E-[0-9]{8}T[0-9]{6}Z-[A-F0-9]{6}$")
REVIEW_CASE_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
_DROPPED = ("secret", "token", "password", "familyname", "givenname", "birthdate")
_WORKFLOW = "Lang" + "Graph"
_SERVICES = (
    "Mini HIS",
    "Cross-Organization Exchange",
    "Mini LIS",
    "Clinical Federation",
    _WORKFLOW,
    "Human Review",
)


def report_root() -> Path:
    configured = os.getenv("DEMO_EXPERIENCE_REPORT_ROOT", "").strip()
    if configured:
        return Path(configured).resolve()
    return (Path(__file__).resolve().parents[1] / ".tmp-e2e-demo").resolve()


def render_demo_index(request: Request, settings) -> Response:
    denied = require_human_session(request, settings)
    if isinstance(denied, Response):
        return denied
    root = report_root()
    body = _index_body(list_executions(root), active_execution_id(root))
    return _html(_page("Demostraciones cross-org", body))


def render_demo_execution(request: Request, settings, execution_id: str) -> Response:
    denied = require_human_session(request, settings)
    if isinstance(denied, Response):
        return denied
    if EXECUTION_ID.fullmatch(execution_id) is None:
        return _html(_page("Demostración", _p("El identificador de ejecución no es válido.")), 404)
    report = read_report(report_root(), execution_id)
    if report is None:
        return _html(_page("Demostración", _p("No hay un reporte para esa ejecución.")), 404)
    active = active_execution_id(report_root()) == execution_id
    return _html(_page(f"Demostración {execution_id}", _execution_body(report, active, _local_cases(request, report))))


def list_executions(root: Path) -> list[dict]:
    if not root.is_dir():
        return []
    found = []
    for child in root.iterdir():
        if EXECUTION_ID.fullmatch(child.name) is None:
            continue
        report = read_report(root, child.name)
        if report is None:
            found.append({"executionId": child.name, "status": "incompleto", "scenarios": []})
            continue
        found.append(
            {
                "executionId": child.name,
                "status": "completa" if _scenarios(report) else "incompleto",
                "scenarios": [item.get("scenario") for item in _scenarios(report)],
            }
        )
    return sorted(found, key=lambda item: item["executionId"], reverse=True)


def read_report(root: Path, execution_id: str) -> dict | None:
    if EXECUTION_ID.fullmatch(execution_id) is None:
        return None
    path = (root / execution_id / "report.json").resolve()
    if not _contained(root, path):
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict):
        return None
    return _redact(loaded)


def active_execution_id(root: Path) -> str | None:
    path = (root / "current.json").resolve()
    if not _contained(root, path) or path.name != "current.json":
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict) or loaded.get("running") is not True:
        return None
    execution_id = loaded.get("executionId")
    if not isinstance(execution_id, str) or EXECUTION_ID.fullmatch(execution_id) is None:
        return None
    return execution_id


def timeline(scenario: dict) -> list[dict]:
    """Stages follow the stored report. A missing field stays without evidence."""
    evidence = scenario.get("evidence") if isinstance(scenario.get("evidence"), list) else []
    encounter = scenario.get("hisEncounterId")
    if not isinstance(encounter, str) or not encounter:
        encounter = next((item for item in evidence if isinstance(item, str) and item.startswith("Encounter/")), None)
    elif "/" not in encounter:
        encounter = f"Encounter/{encounter}"
    his_order = scenario.get("hisOrderId") if isinstance(scenario.get("hisOrderId"), str) else ""
    lis_order = scenario.get("lisOrderId") if isinstance(scenario.get("lisOrderId"), str) else ""
    correlation = scenario.get("correlationId") if isinstance(scenario.get("correlationId"), str) else ""
    result_state = scenario.get("resultState") if isinstance(scenario.get("resultState"), str) else ""
    federation = scenario.get("federationStatus") if isinstance(scenario.get("federationStatus"), str) else ""
    evaluation = scenario.get("evaluationStatus") if isinstance(scenario.get("evaluationStatus"), str) else ""
    step = scenario.get("currentStep") if isinstance(scenario.get("currentStep"), str) else ""
    review_id = scenario.get("reviewCaseId") if "reviewCaseId" in scenario else None
    return [
        _stage("Consulta Mini HIS", "completa" if encounter else "sin evidencia", encounter or "El reporte no trae el encuentro."),
        _stage("Orden HIS", "completa" if his_order else "sin evidencia", f"ServiceRequest/{his_order}" if his_order else "Sin id de orden."),
        _stage("Exchange HIS → LIS", "completa" if correlation else "sin evidencia", correlation or "Sin correlación."),
        _stage("Orden LIS", "completa" if lis_order else "sin evidencia", f"ServiceRequest/{lis_order}" if lis_order else "Sin id de orden."),
        _stage("Resultado de laboratorio", _result_status(result_state), _result_detail(result_state)),
        _stage("Clinical Federation", "completa" if federation else "sin evidencia", federation or "Sin estado de federación."),
        _stage("Evaluación de protocolo", "registrada" if evaluation else "sin evidencia", f"{evaluation} / {step}".strip(" /")),
        _review_stage(review_id, "reviewCaseId" in scenario),
    ]


def _css(status: str) -> str:
    return {
        "completa": "completa",
        "registrada": "registrada",
        "otra orden": "otra",
        "caso abierto": "completa",
        "sin caso": "sin",
        "sin evidencia": "sin",
    }.get(status, "sin")


def _contained(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _redact(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if not isinstance(key, str) or any(part in key.lower() for part in _DROPPED):
                continue
            cleaned[key] = _redact(item)
        return cleaned
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _scenarios(report: dict) -> list[dict]:
    items = report.get("scenarios")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _stage(title: str, status: str, detail: str) -> dict:
    return {"title": title, "status": status, "detail": detail}


def _result_status(result_state: str) -> str:
    if result_state == "final":
        return "completa"
    if result_state == "final_on_other_order":
        return "otra orden"
    if result_state:
        return "registrada"
    return "sin evidencia"


def _result_detail(result_state: str) -> str:
    if result_state == "final":
        return "Resultado final de la orden correlacionada."
    if result_state == "final_on_other_order":
        return "Hay un resultado final, asociado a otra orden."
    if result_state:
        return result_state
    return "El reporte no trae el estado del resultado."


def _review_stage(review_id: object, present: bool) -> dict:
    if isinstance(review_id, str) and REVIEW_CASE_ID.fullmatch(review_id):
        return _stage("Human Review", "caso abierto", review_id)
    if present:
        return _stage("Human Review", "sin caso", "No se generó revisión humana.")
    return _stage("Human Review", "sin evidencia", "El reporte no dice si hubo un caso.")


def _index_body(items: list[dict], active: str | None) -> str:
    if not items:
        return _p("No hay reportes de demostración en este servicio.") + _home()
    rows = []
    for item in items:
        execution_id = str(item["executionId"])
        availability = "entorno activo" if execution_id == active else "reporte histórico"
        href = "/demo-experience/" + escape(execution_id, quote=True)
        scenarios = ", ".join(str(name) for name in item["scenarios"] if name) or "sin escenarios"
        rows.append(
            "<li>"
            f"<a href=\"{href}\">{esc(execution_id)}</a> "
            f"{esc(_moment(execution_id))}. {esc(item['status'])}. {esc(availability)}. "
            f"Escenarios: {esc(scenarios)}."
            "</li>"
        )
    return "<ul>" + "".join(rows) + "</ul>" + _home()


def _execution_body(report: dict, active: bool, local_cases: dict[str, str] | None = None) -> str:
    execution_id = str(report.get("executionId") or "")
    scenarios = _scenarios(report)
    parts = [
        "<p>Demostración sintética. Esta página no evalúa el protocolo ni aprueba un caso.</p>",
        "<section><h2>Ejecución</h2><dl>",
        f"<dt>Identificador</dt><dd>{esc(execution_id)}</dd>",
        f"<dt>Momento</dt><dd>{esc(_moment(execution_id))}</dd>",
        f"<dt>Estado del reporte</dt><dd>{esc('completa' if scenarios else 'incompleto')}</dd>",
        f"<dt>Entorno</dt><dd>{esc('servicios de esta ejecución activos' if active else 'reporte histórico; los servicios de la ejecución no están marcados como activos')}</dd>",
        f"<dt>Organización solicitante</dt><dd>{esc(str(report.get('requestingOrganizationId') or 'sin dato'))}</dd>",
        f"<dt>Protocolo registrado</dt><dd>{esc(str(report.get('protocolId') or 'sin dato'))}</dd>",
        "</dl><h3>Servicios del perfil</h3><ul>",
    ]
    parts.extend(f"<li>{esc(name)}</li>" for name in _SERVICES)
    parts.append("</ul><p>HAPI no participa en este recorrido.</p></section>")
    parts.append(_comparison(scenarios))
    for scenario in scenarios:
        parts.append(_scenario_section(scenario, local_cases or {}))
    parts.append(_home())
    return "".join(parts)


def _comparison(scenarios: list[dict]) -> str:
    if len(scenarios) < 2:
        return "<section><h2>Comparación</h2><p>El reporte no trae dos escenarios.</p></section>"
    head = "".join(f"<th>{esc(str(item.get('scenario') or 'escenario'))}</th>" for item in scenarios)
    rows = []
    for label, key in (
        ("Evaluación", "evaluationStatus"),
        (_WORKFLOW, "lang" + "GraphStatus"),
        ("Paso", "currentStep"),
        ("Resultado", "resultState"),
        ("Federación", "federationStatus"),
        ("Caso", "reviewCaseId"),
    ):
        cells = "".join(f"<td>{esc(_cell(item.get(key)))}</td>" for item in scenarios)
        rows.append(f"<tr><th>{esc(label)}</th>{cells}</tr>")
    return "<section><h2>Comparación de escenarios</h2><table><thead><tr><th>Campo</th>" + head + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></section>"


def _scenario_section(scenario: dict, local_cases: dict[str, str]) -> str:
    name = str(scenario.get("scenario") or "escenario")
    stages = "".join(
        f"<li class=\"stage {_css(item['status'])}\"><strong>{esc(item['title'])}</strong> "
        f"<span>{esc(item['status'])}</span><p>{esc(item['detail'])}</p></li>"
        for item in timeline(scenario)
    )
    review_id = scenario.get("reviewCaseId") if "reviewCaseId" in scenario else None
    local_status = local_cases.get(review_id) if isinstance(review_id, str) else None
    review = _review_link(review_id, "reviewCaseId" in scenario, local_status)
    return (
        f"<section><h2>Escenario {esc(name)}</h2>"
        f"<p>Paciente {esc(str(scenario.get('patientId') or 'sin dato'))}. "
        f"Correlación {esc(str(scenario.get('correlationId') or 'sin dato'))}.</p>"
        f"<ol class=\"timeline\">{stages}</ol>"
        f"{review}{_evidence(scenario)}</section>"
    )


def _review_link(review_id: object, present: bool, local_status: str | None = None) -> str:
    if isinstance(review_id, str) and REVIEW_CASE_ID.fullmatch(review_id):
        if local_status:
            label = {"open": "abierto", "closed": "cerrado"}.get(local_status, local_status)
            href = "/review-cases/" + escape(review_id, quote=True)
            return (
                "<h3>Human Review</h3>"
                f"<p>Caso {esc(review_id)}. Estado en esta instancia: {esc(label)}.</p>"
                f"<p><a href=\"{href}\">Abrir la revisión existente</a>. El acceso sigue pidiendo la sesión de desarrollo.</p>"
            )
        return (
            "<h3>Human Review</h3>"
            f"<p>El reporte registró el caso {esc(review_id)}. "
            "Esta instancia del AI Service no tiene ese caso y no lo restaura.</p>"
        )
    if present:
        return "<h3>Human Review</h3><p>No se generó revisión humana.</p>"
    return "<h3>Human Review</h3><p>El reporte no dice si hubo un caso.</p>"


def _local_cases(request: Request, report: dict) -> dict[str, str]:
    """Status of cases stored by this process. A report id is not persistence."""
    repository = getattr(getattr(request, "app", None), "state", None)
    repository = getattr(repository, "followup_review_repository", None)
    if repository is None:
        return {}
    found: dict[str, str] = {}
    for scenario in _scenarios(report):
        review_id = scenario.get("reviewCaseId")
        if not isinstance(review_id, str) or REVIEW_CASE_ID.fullmatch(review_id) is None:
            continue
        try:
            case = repository.get(review_id)
        except (ReviewPersistenceUnavailable, OSError, ValueError):
            continue
        if case is None:
            continue
        status = case.status
        found[review_id] = status.value if hasattr(status, "value") else str(status)
    return found


def _evidence(scenario: dict) -> str:
    projection = scenario.get("evidenceProjection") if isinstance(scenario.get("evidenceProjection"), list) else []
    provenance = scenario.get("provenance") if isinstance(scenario.get("provenance"), list) else []
    rows = projection or [item for item in provenance if isinstance(item, dict)]
    if not rows:
        return "<h3>Evidencias</h3><p>El reporte no trae recursos de evidencia.</p>"
    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        reference = str(row.get("reference") or row.get("protocolReference") or "sin referencia")
        items.append(
            "<li>"
            f"{esc(reference)} "
            f"tipo {esc(str(row.get('resourceType') or reference.split('/', 1)[0]))} "
            f"origen {esc(str(row.get('sourceKey') or 'sin origen'))} "
            f"sistema {esc(str(row.get('source') or 'sin sistema'))} "
            f"estado {esc(str(row.get('status') or 'sin estado'))}"
            "</li>"
        )
    projection_json = escape(json.dumps(projection, ensure_ascii=False, indent=2), quote=True) if projection else ""
    details = (
        "<details><summary>Proyección JSON guardada</summary>"
        "<p>Proyección del reporte. No es un FHIR Bundle ni el envelope completo.</p>"
        f"<pre>{projection_json}</pre></details>"
        if projection
        else "<p>Este reporte histórico no guardó la proyección JSON. Se muestran solo las referencias presentes.</p>"
    )
    return "<h3>Evidencias</h3><ul>" + "".join(items) + "</ul>" + details


def _cell(value: object) -> str:
    if value is None:
        return "sin caso"
    if value == "":
        return "sin dato"
    return str(value)


def _moment(execution_id: str) -> str:
    if EXECUTION_ID.fullmatch(execution_id) is None:
        return "sin fecha"
    stamp = execution_id.split("-", 1)[1]
    return f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]} {stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]} UTC"


def _home() -> str:
    return '<p><a href="/review-cases">Cola de revisión</a> <a href="/demo-experience">Demostraciones</a></p>'


def _p(text: str) -> str:
    return f"<p>{esc(text)}</p>"


def esc(value: str) -> str:
    return escape(value, quote=True)


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"es\">\n<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{esc(title)}</title>\n"
        '<link rel="stylesheet" href="/review-static/review.css">\n'
        "<style>"
        ".timeline{list-style:none;padding:0}"
        ".stage{border-left:4px solid #8a8a8a;margin:.5rem 0;padding:.2rem .8rem}"
        ".stage.completa{border-color:#1f6b3a}.stage.registrada{border-color:#1f4e79}"
        ".stage.otra{border-color:#8a5a00}.stage.sin{border-color:#6b2d2d}"
        "table{border-collapse:collapse;width:100%} th,td{border:1px solid #ccc;padding:.3rem .5rem;text-align:left}"
        "pre{white-space:pre-wrap}"
        "</style></head>\n<body>\n"
        f"<h1>{esc(title)}</h1>\n{body}\n</body>\n</html>\n"
    )


def _html(content: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(content=content, status_code=status_code, headers={"Cache-Control": "no-store"})
