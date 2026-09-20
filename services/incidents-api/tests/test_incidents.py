"""Tests integrales para los endpoints de incidents CRUD + summary.

Cubre todos los 7 endpoints:
  - POST   /api/incidents          (crear)
  - GET    /api/incidents          (listar con filtros)
  - GET    /api/incidents/summary  (resumen)
  - GET    /api/incidents/{id}     (obtener uno)
  - PATCH  /api/incidents/{id}     (actualizar)
  - PATCH  /api/incidents/{id}/status (transición de estado)
  - DELETE /api/incidents/{id}     (eliminar)

Por cada endpoint: happy path, edge cases, failure modes.
"""

from __future__ import annotations

import pytest
from tests.helpers import MINIMAL_BODY, seed_incident


# =========================================================================
#  POST /api/incidents — Crear incidente
# =========================================================================

class TestCreateIncident:
    """POST /api/incidents"""

    # ── Happy path ─────────────────────────────────────────────────────

    @pytest.mark.parametrize("origin", ["customer", "branch", "internal"])
    def test_create_happy_path(self, client, incidents_table, origin):
        payload = {**MINIMAL_BODY, "origin": origin}
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == payload["title"]
        assert data["branch"] == payload["branch"]
        assert data["origin"] == origin
        assert data["category"] == payload["category"]
        assert data["status"] == "open"
        assert isinstance(data["id"], int)
        assert data["created_at"] is not None
        assert data["updated_at"] is not None
        # Verifica que el registro se guardó en TinyDB
        assert incidents_table.get(doc_id=data["id"]) is not None

    def test_create_all_categories(self, client):
        """Prueba cada categoría válida."""
        for cat in [
            "clinical_equipment", "it_system", "billing_error",
            "compliance_breach", "patient_experience", "staff_issue",
            "facility_issue", "referral_issue", "other",
        ]:
            payload = {**MINIMAL_BODY, "category": cat, "title": f"Test {cat}"}
            resp = client.post("/api/incidents", json=payload)
            assert resp.status_code == 201, f"Failed for category '{cat}': {resp.json()}"
            assert resp.json()["category"] == cat

    def test_create_all_branches(self, client):
        """Prueba cada sucursal válida."""
        branches = [
            "central", "austin_north", "dallas_uptown", "houston_med_center",
            "san_antonio_west", "miami_brickell", "miami_doral", "orlando_east",
            "tampa_bay", "atlanta_midtown", "savannah", "london_city",
            "london_west", "manchester_central",
        ]
        for b in branches:
            payload = {**MINIMAL_BODY, "branch": b, "title": f"Test {b}"}
            resp = client.post("/api/incidents", json=payload)
            assert resp.status_code == 201, f"Failed for branch '{b}': {resp.json()}"
            assert resp.json()["branch"] == b

    # ── Edge cases ────────────────────────────────────────────────────

    def test_create_explicit_status_not_open(self, client):
        """status explícito distinto de OPEN debe respetarse."""
        payload = {**MINIMAL_BODY, "status": "in_progress"}
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 201
        assert resp.json()["status"] == "in_progress"

    def test_create_short_title_min_length(self, client):
        """Título de exactamente 2 caracteres (mínimo permitido)."""
        payload = {**MINIMAL_BODY, "title": "AB"}
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 201
        assert resp.json()["title"] == "AB"

    def test_create_long_title_max_length(self, client):
        """Título de 200 caracteres."""
        title = "A" * 200
        payload = {**MINIMAL_BODY, "title": title}
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 201
        assert resp.json()["title"] == title

    def test_create_min_description(self, client):
        """Descripción de exactamente 10 caracteres."""
        payload = {**MINIMAL_BODY, "description": "A" * 10}
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 201

    def test_create_max_description(self, client):
        """Descripción de 2000 caracteres."""
        payload = {**MINIMAL_BODY, "description": "A" * 2000}
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 201

    # ── Failure modes ─────────────────────────────────────────────────

    def test_create_missing_title(self, client):
        payload = {
            "description": "Descripción válida para prueba",
            "category": "it_system",
            "origin": "internal",
            "branch": "central",
        }
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 422

    def test_create_missing_description(self, client):
        payload = {
            "title": "Incidente sin descripción",
            "category": "it_system",
            "origin": "internal",
            "branch": "central",
        }
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 422

    def test_create_missing_category(self, client):
        payload = {
            "title": "Incidente sin categoría",
            "description": "Descripción válida para prueba.",
            "origin": "internal",
            "branch": "central",
        }
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 422

    def test_create_missing_origin(self, client):
        payload = {
            "title": "Incidente sin origen",
            "description": "Descripción válida para prueba.",
            "category": "it_system",
            "branch": "central",
        }
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 422

    def test_create_missing_branch(self, client):
        payload = {
            "title": "Incidente sin branch",
            "description": "Descripción válida para prueba.",
            "category": "it_system",
            "origin": "internal",
        }
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 422

    def test_create_empty_body(self, client):
        resp = client.post("/api/incidents", json={})
        assert resp.status_code == 422

    def test_create_invalid_branch(self, client):
        payload = {**MINIMAL_BODY, "branch": "nonexistent_branch"}
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 422
        err = resp.json()
        assert "Invalid branch" in str(err)

    def test_create_invalid_category(self, client):
        payload = {**MINIMAL_BODY, "category": "invalid_cat"}
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 422

    def test_create_invalid_origin(self, client):
        payload = {**MINIMAL_BODY, "origin": "invalid_origin"}
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 422

    def test_create_invalid_status(self, client):
        payload = {**MINIMAL_BODY, "status": "invalid_status"}
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 422

    def test_create_title_too_short(self, client):
        payload = {**MINIMAL_BODY, "title": "A"}
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 422

    def test_create_title_too_long(self, client):
        payload = {**MINIMAL_BODY, "title": "A" * 201}
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 422

    def test_create_description_too_short(self, client):
        payload = {**MINIMAL_BODY, "description": "A" * 9}
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 422

    def test_create_description_too_long(self, client):
        payload = {**MINIMAL_BODY, "description": "A" * 2001}
        resp = client.post("/api/incidents", json=payload)
        assert resp.status_code == 422


# =========================================================================
#  GET /api/incidents/{id} — Obtener un incidente
# =========================================================================

class TestGetIncident:
    """GET /api/incidents/{incident_id}"""

    def test_get_happy_path(self, client, incidents_table):
        doc_id = seed_incident(incidents_table)
        resp = client.get(f"/api/incidents/{doc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == doc_id
        assert data["title"] == MINIMAL_BODY["title"]
        assert data["branch"] == MINIMAL_BODY["branch"]

    def test_get_returns_branch_label(self, client, incidents_table):
        doc_id = seed_incident(incidents_table, branch="miami_brickell")
        resp = client.get(f"/api/incidents/{doc_id}")
        data = resp.json()
        assert data["branch_label"] == "Miami Brickell"
        assert data["branch"] == "miami_brickell"

    def test_get_nonexistent_returns_404(self, client):
        resp = client.get("/api/incidents/99999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_invalid_id_format(self, client):
        resp = client.get("/api/incidents/abc")
        assert resp.status_code == 422


# =========================================================================
#  GET /api/incidents — Listar con filtros
# =========================================================================

class TestListIncidents:
    """GET /api/incidents"""

    def test_list_empty(self, client):
        resp = client.get("/api/incidents")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_multiple(self, client, incidents_table):
        seed_incident(incidents_table)
        seed_incident(incidents_table, title="Segundo", category="it_system")
        resp = client.get("/api/incidents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_list_filter_by_status(self, client, incidents_table):
        seed_incident(incidents_table, status="open")
        seed_incident(incidents_table, title="Cerrado", status="resolved")
        resp = client.get("/api/incidents?status=open")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["status"] == "open"

    def test_list_filter_by_category(self, client, incidents_table):
        seed_incident(incidents_table, category="clinical_equipment")
        seed_incident(incidents_table, title="IT", category="it_system")
        resp = client.get("/api/incidents?category=it_system")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["category"] == "it_system"

    def test_list_filter_by_origin(self, client, incidents_table):
        seed_incident(incidents_table, origin="branch")
        seed_incident(incidents_table, title="Interno", origin="internal")
        resp = client.get("/api/incidents?origin=branch")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["origin"] == "branch"

    def test_list_filter_by_branch(self, client, incidents_table):
        seed_incident(incidents_table, branch="central")
        seed_incident(incidents_table, title="Austin", branch="austin_north")
        resp = client.get("/api/incidents?branch=central")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["branch"] == "central"

    def test_list_filter_no_match(self, client, incidents_table):
        seed_incident(incidents_table)
        resp = client.get("/api/incidents?status=resolved")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_filter_multiple(self, client, incidents_table):
        seed_incident(incidents_table, origin="branch", status="open")
        seed_incident(incidents_table, title="Otro", origin="internal", status="open")
        resp = client.get("/api/incidents?origin=branch&status=open")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_filter_invalid_status(self, client):
        resp = client.get("/api/incidents?status=invalid")
        assert resp.status_code == 422


# =========================================================================
#  GET /api/incidents/summary — Resumen
# =========================================================================

class TestIncidentSummary:
    """GET /api/incidents/summary"""

    def test_summary_empty_db(self, client):
        resp = client.get("/api/incidents/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["by_status"] == {}
        assert data["by_category"] == {}
        assert data["by_branch"] == {}
        assert data["by_origin"] == {}

    def test_summary_counts(self, client, incidents_table):
        seed_incident(incidents_table, status="open", category="clinical_equipment", origin="branch", branch="central")
        seed_incident(incidents_table, title="Segundo", status="open", category="it_system", origin="internal", branch="austin_north")
        seed_incident(incidents_table, title="Tercero", status="resolved", category="clinical_equipment", origin="branch", branch="central")

        resp = client.get("/api/incidents/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["by_status"]["open"] == 2
        assert data["by_status"]["resolved"] == 1
        assert data["by_category"]["clinical_equipment"] == 2
        assert data["by_category"]["it_system"] == 1
        assert data["by_branch"]["central"] == 2
        assert data["by_branch"]["austin_north"] == 1
        assert data["by_origin"]["branch"] == 2
        assert data["by_origin"]["internal"] == 1


# =========================================================================
#  PATCH /api/incidents/{id} — Actualizar incidente
# =========================================================================

class TestUpdateIncident:
    """PATCH /api/incidents/{incident_id}"""

    def test_update_title(self, client, incidents_table):
        doc_id = seed_incident(incidents_table)
        resp = client.patch(f"/api/incidents/{doc_id}", json={"title": "Nuevo título"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Nuevo título"
        # El resto de campos debe permanecer igual
        assert data["description"] == MINIMAL_BODY["description"]

    def test_update_all_fields(self, client, incidents_table):
        doc_id = seed_incident(incidents_table)
        resp = client.patch(f"/api/incidents/{doc_id}", json={
            "title": "Actualizado",
            "description": "Descripción completamente nueva.",
            "category": "billing_error",
            "status": "in_progress",
            "branch": "dallas_uptown",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Actualizado"
        assert data["description"] == "Descripción completamente nueva."
        assert data["category"] == "billing_error"
        assert data["status"] == "in_progress"
        assert data["branch"] == "dallas_uptown"

    def test_update_partial_single_field(self, client, incidents_table):
        doc_id = seed_incident(incidents_table)
        resp = client.patch(f"/api/incidents/{doc_id}", json={"description": "Nueva descripción para este incidente."})
        assert resp.status_code == 200
        assert resp.json()["description"] == "Nueva descripción para este incidente."

    def test_update_updates_updated_at(self, client, incidents_table):
        doc_id = seed_incident(incidents_table)
        resp = client.patch(f"/api/incidents/{doc_id}", json={"title": "Nuevo"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated_at"] != data["created_at"]

    def test_update_nonexistent_returns_404(self, client):
        resp = client.patch("/api/incidents/99999", json={"title": "Nope"})
        assert resp.status_code == 404

    def test_update_invalid_branch(self, client, incidents_table):
        doc_id = seed_incident(incidents_table)
        resp = client.patch(f"/api/incidents/{doc_id}", json={"branch": "invalid"})
        assert resp.status_code == 422

    def test_update_title_too_short(self, client, incidents_table):
        doc_id = seed_incident(incidents_table)
        resp = client.patch(f"/api/incidents/{doc_id}", json={"title": "X"})
        assert resp.status_code == 422

    def test_update_empty_body(self, client, incidents_table):
        """Enviar body vacío = no hay cambios, pero es válido."""
        doc_id = seed_incident(incidents_table)
        resp = client.patch(f"/api/incidents/{doc_id}", json={})
        assert resp.status_code == 200
        assert resp.json()["title"] == MINIMAL_BODY["title"]


# =========================================================================
#  PATCH /api/incidents/{id}/status — Transición de estado
# =========================================================================

class TestStatusTransition:
    """PATCH /api/incidents/{incident_id}/status"""

    VALID_TRANSITIONS = [
        ("open", "in_progress"),
        ("open", "discarded"),
        ("in_progress", "resolved"),
        ("in_progress", "discarded"),
    ]

    INVALID_TRANSITIONS = [
        ("open", "resolved"),
        ("resolved", "open"),
        ("resolved", "in_progress"),
        ("resolved", "discarded"),
        ("discarded", "open"),
        ("discarded", "in_progress"),
        ("discarded", "resolved"),
    ]

    @pytest.mark.parametrize("from_status,to_status", VALID_TRANSITIONS)
    def test_valid_transition(self, client, incidents_table, from_status, to_status):
        doc_id = seed_incident(incidents_table, status=from_status)
        resp = client.patch(f"/api/incidents/{doc_id}/status", json={"status": to_status})
        assert resp.status_code == 200, f"Failed: {from_status} -> {to_status}: {resp.json()}"
        assert resp.json()["status"] == to_status

    @pytest.mark.parametrize("from_status,to_status", INVALID_TRANSITIONS)
    def test_invalid_transition(self, client, incidents_table, from_status, to_status):
        doc_id = seed_incident(incidents_table, status=from_status)
        resp = client.patch(f"/api/incidents/{doc_id}/status", json={"status": to_status})
        assert resp.status_code == 400, f"Should reject: {from_status} -> {to_status}"
        assert "Invalid status transition" in resp.json()["detail"]
        assert from_status in resp.json()["detail"]
        assert to_status in resp.json()["detail"]

    def test_transition_nonexistent_returns_404(self, client):
        resp = client.patch("/api/incidents/99999/status", json={"status": "in_progress"})
        assert resp.status_code == 404

    def test_transition_missing_status_field(self, client, incidents_table):
        doc_id = seed_incident(incidents_table)
        resp = client.patch(f"/api/incidents/{doc_id}/status", json={})
        assert resp.status_code == 422

    def test_transition_invalid_status_value(self, client, incidents_table):
        doc_id = seed_incident(incidents_table)
        resp = client.patch(f"/api/incidents/{doc_id}/status", json={"status": "invalid"})
        assert resp.status_code == 422


# =========================================================================
#  DELETE /api/incidents/{id} — Eliminar incidente
# =========================================================================

class TestDeleteIncident:
    """DELETE /api/incidents/{incident_id}"""

    def test_delete_happy_path(self, client, incidents_table):
        doc_id = seed_incident(incidents_table)
        resp = client.delete(f"/api/incidents/{doc_id}")
        assert resp.status_code == 204
        # Verifica que ya no exista
        get_resp = client.get(f"/api/incidents/{doc_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete("/api/incidents/99999")
        assert resp.status_code == 404

    def test_delete_then_list_empty(self, client, incidents_table):
        doc_id = seed_incident(incidents_table)
        client.delete(f"/api/incidents/{doc_id}")
        resp = client.get("/api/incidents")
        assert resp.json() == []

    def test_delete_updates_summary(self, client, incidents_table):
        seed_incident(incidents_table)
        doc_id2 = seed_incident(incidents_table, title="Segundo")
        client.delete(f"/api/incidents/{doc_id2}")
        summary = client.get("/api/incidents/summary").json()
        assert summary["total"] == 1


# =========================================================================
#  Smoke: rutas base y documentación
# =========================================================================

class TestRootEndpoint:
    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "HealthCore Incidents API"
        assert "/api/incidents" in data["incidents"]
        assert "/api/incidents/summary" in data["summary"]

    def test_openapi_schema(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200