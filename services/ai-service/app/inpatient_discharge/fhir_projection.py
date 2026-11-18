"""FHIR R4 collection projected from a Mini HIS chart. It adds no diagnosis."""


def project_chart(chart):
    patient = chart["patientId"]
    episode = chart["episodeId"]
    entries = [_entry({
        "resourceType": "Encounter",
        "id": episode,
        "status": "finished" if chart["status"] == "closed" else "in-progress",
        "subject": {"reference": f"Patient/{patient}"},
        "meta": {"versionId": str(chart["version"]), "source": "mini-his"},
    })]
    for note in chart["notes"]:
        text = "contenido retenido" if note.get("withheld") else note.get("text") or ""
        entries.append(_observation(note["id"], patient, episode, text))
    for result in chart["results"]:
        entries.append(_observation(result["id"], patient, episode, f"{result['value']} {result['unit']}"))
        entries.append(_entry({
            "resourceType": "DiagnosticReport",
            "id": "report-" + result["id"],
            "status": "final",
            "subject": {"reference": f"Patient/{patient}"},
            "encounter": {"reference": f"Encounter/{episode}"},
            "result": [{"reference": f"Observation/{result['id']}"}],
        }))
    for allergy in chart["allergies"]:
        entries.append(_entry({
            "resourceType": "AllergyIntolerance",
            "id": allergy["id"],
            "patient": {"reference": f"Patient/{patient}"},
            "code": {"text": allergy["substance"]},
        }))
    for medication in chart["medications"]:
        entries.append(_entry({
            "resourceType": "MedicationStatement",
            "id": medication["id"],
            "status": medication["status"],
            "subject": {"reference": f"Patient/{patient}"},
            "medicationCodeableConcept": {"text": medication["name"]},
        }))
    activities = []
    for task in chart["tasks"]:
        entries.append(_entry({
            "resourceType": "Task",
            "id": task["id"],
            "status": "completed" if task["status"] == "resolved" else "requested",
            "intent": "order",
            "for": {"reference": f"Patient/{patient}"},
            "encounter": {"reference": f"Encounter/{episode}"},
            "description": task["title"],
        }))
        activities.append({"reference": {"reference": f"Task/{task['id']}"}})
    entries.append(_entry({
        "resourceType": "CarePlan",
        "id": "plan-" + episode,
        "status": "active",
        "intent": "plan",
        "subject": {"reference": f"Patient/{patient}"},
        "encounter": {"reference": f"Encounter/{episode}"},
        "activity": activities,
    }))
    entries.append(_entry({
        "resourceType": "Composition",
        "id": "draft-" + episode,
        "status": "preliminary",
        "title": "Borrador de preparacion de alta",
        "subject": {"reference": f"Patient/{patient}"},
        "encounter": {"reference": f"Encounter/{episode}"},
    }))
    return {"resourceType": "Bundle", "type": "collection", "entry": entries}


def _observation(resource_id, patient, episode, text):
    return _entry({
        "resourceType": "Observation",
        "id": resource_id,
        "status": "final",
        "subject": {"reference": f"Patient/{patient}"},
        "encounter": {"reference": f"Encounter/{episode}"},
        "valueString": text,
    })


def _entry(resource):
    return {"resource": resource}
