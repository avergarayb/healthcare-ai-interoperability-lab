"""Strict discharge draft. The model may not close an encounter or add a diagnosis."""
import hashlib
import json

ALLOWED_KEYS = {
    "kind", "review", "checklistComplete", "statements", "pending",
    "proposedTasks", "abstentions", "protocols", "closesEncounter",
}
BANNED = ("ignore previous", "diagnost", "prescri", "system prompt")


def build_draft(chart, protocols):
    open_tasks = [task["id"] for task in chart["tasks"] if task["kind"] == "ward" and task["status"] == "open"]
    gaps = _gaps(chart)
    complete = not open_tasks and not gaps
    protocol_id = "discharge-preparation" if complete else "pending-verification"
    statements = [{
        "text": "El episodio sigue abierto. Esta preparacion no cierra la hospitalizacion.",
        "sources": [{"source": "mini-his", "resourceType": "Encounter", "id": chart["episodeId"]}],
    }]
    if open_tasks:
        statements.append({
            "text": "Hay tareas de planta abiertas. El checklist no esta completo.",
            "sources": [{"source": "mini-his", "resourceType": "Task", "id": open_tasks[0]}],
        })
    elif complete:
        statements.append({
            "text": "Los pendientes de planta registrados estan resueltos. El checklist de preparacion esta completo.",
            "sources": [{"source": "protocol", "resourceType": "DocumentReference", "id": protocol_id}],
        })
    else:
        statements.append({
            "text": "Falta informacion documentada. El checklist no esta completo.",
            "sources": [{"source": "protocol", "resourceType": "DocumentReference", "id": protocol_id}],
        })
    abstentions = []
    if chart["contradictions"]:
        abstentions.append("medication_contradiction")
    if any(note.get("withheld") for note in chart["notes"]):
        abstentions.append("note_withheld")
    proposed = []
    if complete:
        proposed.append({"key": "continuity-follow-up", "title": "Coordinar seguimiento documentado"})
    return {
        "kind": "discharge_preparation",
        "review": "pending_human_review",
        "checklistComplete": complete,
        "statements": statements,
        "pending": open_tasks,
        "proposedTasks": proposed,
        "abstentions": abstentions,
        "protocols": [{"id": item["id"], "version": item["version"], "section": item["section"]} for item in protocols],
        "closesEncounter": False,
    }


def validate_draft(draft, chart, protocols):
    if type(draft) is not dict or set(draft) != ALLOWED_KEYS:
        return "draft_rejected"
    if draft["kind"] != "discharge_preparation" or draft["review"] != "pending_human_review":
        return "draft_rejected"
    if draft["closesEncounter"] is not False:
        return "draft_rejected"
    open_tasks = [task["id"] for task in chart["tasks"] if task["kind"] == "ward" and task["status"] == "open"]
    complete = not open_tasks and not _gaps(chart)
    if draft["checklistComplete"] is not complete or draft["pending"] != open_tasks:
        return "draft_rejected"
    if chart["contradictions"] and "medication_contradiction" not in draft["abstentions"]:
        return "draft_rejected"
    allowed_ids = _ids(chart, protocols)
    for statement in draft["statements"]:
        text = statement.get("text") if type(statement) is dict else ""
        if type(text) is not str or not text or len(text) > 400:
            return "draft_rejected"
        lowered = text.lower()
        if any(token in lowered for token in BANNED):
            return "draft_rejected"
        sources = statement.get("sources")
        if type(sources) is not list or not sources:
            return "draft_rejected"
        for source in sources:
            if type(source) is not dict or source.get("id") not in allowed_ids:
                return "draft_rejected"
    cited = {item.get("id") for item in draft["protocols"] if type(item) is dict}
    if not cited or not cited <= {item["id"] for item in protocols}:
        return "draft_rejected"
    if any(note.get("withheld") and note.get("text") for note in chart["notes"]):
        return "draft_rejected"
    return ""


def canonical_hash(draft):
    encoded = json.dumps(draft, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _gaps(chart):
    gaps = []
    if not chart["notes"]:
        gaps.append("notes")
    if not chart["results"]:
        gaps.append("results")
    if not chart["allergies"]:
        gaps.append("allergies")
    if not chart["medications"] or chart["contradictions"]:
        gaps.append("medications")
    return gaps


def _ids(chart, protocols):
    found = {chart["episodeId"]}
    for key in ("notes", "allergies", "medications", "tasks", "results"):
        found.update(item["id"] for item in chart[key])
    found.update(item["id"] for item in protocols)
    return found
