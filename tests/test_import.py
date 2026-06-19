"""
Tests for bulk lead import (CSV / Excel):
header mapping, ownership (imported under the uploader), dedup, validation,
the template download, and scope visibility.
"""

from io import BytesIO

import pytest

from models.lead import Lead
from models.user import User
from routes.auth import get_current_user
from services import lead_importer
from main import app


CSV_BASIC = (
    "Name,Email,Phone,Company,State,Type,Team Size,Wants Demo\n"
    "Rajesh Sharma,rajesh@brokerhouse.in,9876543210,Mehta Brokers,Maharashtra,broker,12,yes\n"
    "Priya Nair,priya@agentpro.in,9123456780,AgentPro,Karnataka,agent,3,no\n"
)


def csv_upload(text):
    return {"file": ("leads.csv", BytesIO(text.encode()), "text/csv")}


def make_employee(db, name="Imp Emp", email="imp@test.in"):
    u = User(name=name, email=email, role="employee", password_hash="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def as_user(user):
    app.dependency_overrides[get_current_user] = lambda: user


# ── Service: parsing & header mapping ─────────────────────────────────────────

class TestParsing:
    def test_csv_rows_and_field_mapping(self):
        rows = lead_importer.parse_rows("leads.csv", CSV_BASIC.encode())
        assert len(rows) == 2
        f = lead_importer.to_lead_fields(rows[0])
        assert f["first_name"] == "Rajesh Sharma"
        assert f["email"] == "rajesh@brokerhouse.in"
        assert f["phone"] == "9876543210"
        assert f["lead_type"] == "broker"
        assert f["team_size"] == 12
        assert f["willing_for_demo"] is True

    def test_aliased_headers(self):
        text = "Full Name,Mobile,Organisation\nAmit,9000000001,Apex\n"
        f = lead_importer.to_lead_fields(lead_importer.parse_rows("x.csv", text.encode())[0])
        assert f["first_name"] == "Amit"
        assert f["phone"] == "9000000001"
        assert f["company_name"] == "Apex"

    def test_unknown_extension_rejected(self):
        with pytest.raises(ValueError):
            lead_importer.parse_rows("data.txt", b"a,b\n1,2\n")

    def test_meta_facebook_export_columns(self):
        # The real marketing sheet is the Meta/Facebook Lead Ads export: long
        # question headers + a "p:" phone prefix. All of it must map.
        header = (
            "platform,"
            "do_you_currently_use_any_software_or_digital_platform_to_manage_your_leads,"
            "are_you_open_to_adopting_a_new_technology_platform_if_it_helps_you,"
            "would_you_be_willing_to_evaluate_a_new_tech_solution_through_a_demo_or_trial,"
            "types_of_business,first_name,email,phone,state,company_name\n"
        )
        row = "fb,no,yes,yes,posp_advisor,Mustafa,m@x.in,p:+919520771486,Uttar Pradesh,Pasha Insurance\n"
        f = lead_importer.to_lead_fields(lead_importer.parse_rows("x.csv", (header + row).encode())[0])
        assert f["first_name"] == "Mustafa"
        assert f["phone"] == "+919520771486"          # "p:" prefix stripped
        assert f["lead_type"] == "posp_advisor"        # types_of_business
        assert f["uses_software"] is False             # long question header
        assert f["open_to_platform"] is True
        assert f["willing_for_demo"] is True
        assert f["source"] == "facebook"               # platform=fb

    def test_xlsx_parsing(self):
        openpyxl = pytest.importorskip("openpyxl")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Name", "Email", "Phone"])
        ws.append(["Sneha", "sneha@x.in", "9111111111"])
        buf = BytesIO()
        wb.save(buf)
        rows = lead_importer.parse_rows("leads.xlsx", buf.getvalue())
        assert len(rows) == 1
        f = lead_importer.to_lead_fields(rows[0])
        assert f["first_name"] == "Sneha"
        assert f["email"] == "sneha@x.in"


# ── Endpoint: import ──────────────────────────────────────────────────────────

class TestImportEndpoint:
    def test_employee_import_assigns_to_self(self, client, db):
        emp = make_employee(db)
        as_user(emp)
        r = client.post("/leads/import", files=csv_upload(CSV_BASIC))
        assert r.status_code == 200
        body = r.json()
        assert body["imported"] == 2
        # An employee can only assign to themselves.
        assert body["assigned"] == [{"owner_id": emp.id, "owner_name": emp.name, "count": 2}]

        leads = db.query(Lead).filter(Lead.owner_id == emp.id).all()
        assert len(leads) == 2
        assert all(l.lead_score is not None and l.status == "new" for l in leads)
        assert {l.email for l in leads} == {"rajesh@brokerhouse.in", "priya@agentpro.in"}

    def test_admin_import_distributes_across_all_employees(self, client, db):
        # Default client user is admin → leads spread across ALL employees,
        # never owned by the admin who uploaded them.
        e1 = make_employee(db, "Emp A", "a@test.in")
        e2 = make_employee(db, "Emp B", "b@test.in")
        e3 = make_employee(db, "Emp C", "c@test.in")
        six = "Name,Email\n" + "".join(f"L{i},l{i}@imp.in\n" for i in range(6))

        r = client.post("/leads/import", files=csv_upload(six))
        body = r.json()
        assert body["imported"] == 6
        per_owner = {a["owner_id"]: a["count"] for a in body["assigned"]}
        assert set(per_owner) == {e1.id, e2.id, e3.id}     # all three employees
        assert all(c == 2 for c in per_owner.values())     # balanced 2 / 2 / 2
        # Every imported lead is owned by an employee, never the uploading admin.
        owners = {l.owner_id for l in db.query(Lead).all()}
        assert all(db.get(User, o).role == "employee" for o in owners)

    def test_manager_import_stays_within_their_team(self, client, db):
        admin = User(name="Admin", email="adm@test.in", role="admin", password_hash="x")
        mgr = User(name="Mgr", email="m@test.in", role="manager", password_hash="x")
        db.add_all([admin, mgr]); db.flush()
        mgr.manager_id = admin.id
        mine1 = make_employee(db, "Mine1", "m1@test.in"); mine1.manager_id = mgr.id
        mine2 = make_employee(db, "Mine2", "m2@test.in"); mine2.manager_id = mgr.id
        outsider = make_employee(db, "Outsider", "out@test.in")  # different team
        db.commit()
        as_user(mgr)

        four = "Name,Email\n" + "".join(f"L{i},lm{i}@imp.in\n" for i in range(4))
        r = client.post("/leads/import", files=csv_upload(four))
        per_owner = {a["owner_id"]: a["count"] for a in r.json()["assigned"]}
        assert set(per_owner) == {mine1.id, mine2.id}      # only the manager's team
        assert outsider.id not in per_owner
        assert db.query(Lead).filter(Lead.owner_id == outsider.id).count() == 0

    def test_duplicate_rows_skipped(self, client, db):
        emp = make_employee(db)
        as_user(emp)
        client.post("/leads/import", files=csv_upload(CSV_BASIC))
        # Re-import the same file → all duplicates, nothing new created.
        r = client.post("/leads/import", files=csv_upload(CSV_BASIC))
        assert r.json()["imported"] == 0
        assert r.json()["duplicates"] == 2
        assert db.query(Lead).filter(Lead.owner_id == emp.id).count() == 2

    def test_within_file_duplicate_collapsed(self, client, db):
        emp = make_employee(db)
        as_user(emp)
        dup = ("Name,Email\n"
               "A,same@x.in\n"
               "B,same@x.in\n")
        r = client.post("/leads/import", files=csv_upload(dup))
        assert r.json()["imported"] == 1
        assert r.json()["duplicates"] == 1

    def test_rows_missing_contact_reported(self, client, db):
        emp = make_employee(db)
        as_user(emp)
        bad = ("Name,Email,Phone\n"
               "NoContact,,\n"
               "Good,good@x.in,\n")
        r = client.post("/leads/import", files=csv_upload(bad))
        body = r.json()
        assert body["imported"] == 1
        assert len(body["errors"]) == 1
        assert body["errors"][0]["row"] == 1

    def test_unsupported_file_400(self, client, db):
        as_user(make_employee(db))
        r = client.post("/leads/import",
                        files={"file": ("data.txt", BytesIO(b"x"), "text/plain")})
        assert r.status_code == 400

    def test_import_requires_login(self, client, db):
        app.dependency_overrides.pop(get_current_user, None)
        r = client.post("/leads/import", files=csv_upload(CSV_BASIC))
        assert r.status_code == 401

    def test_imported_lead_visible_only_to_owner_chain(self, client, db):
        # Two unrelated employees; an import by one is not visible to the other.
        emp1 = make_employee(db, "E1", "e1@test.in")
        emp2 = make_employee(db, "E2", "e2@test.in")
        as_user(emp1)
        client.post("/leads/import", files=csv_upload(CSV_BASIC))

        as_user(emp2)
        listing = client.get("/leads/").json()  # endpoint returns a bare array
        emails = {l.get("email") for l in listing}
        assert "rajesh@brokerhouse.in" not in emails
        assert listing == []  # emp2 owns nothing


class TestAssignmentPolicy:
    def test_pool_by_role(self, db):
        from services.auth_service import assignment_pool
        admin = User(name="A", email="pa@test.in", role="admin", password_hash="x")
        mgr = User(name="M", email="pm@test.in", role="manager", password_hash="x")
        db.add_all([admin, mgr]); db.flush()
        mgr.manager_id = admin.id
        e1 = make_employee(db, "E1", "pe1@test.in"); e1.manager_id = mgr.id
        e2 = make_employee(db, "E2", "pe2@test.in")  # different team
        db.commit()

        assert assignment_pool(None, db) is None      # system source → all
        assert assignment_pool(admin, db) is None      # admin → all
        pool = assignment_pool(mgr, db)
        assert e1.id in pool and e2.id not in pool      # manager → own team
        assert assignment_pool(e1, db) == {e1.id}       # employee → self

    def test_next_owner_respects_among(self, db):
        from models.lead import Lead as L
        from services.auth_service import next_owner_id
        e1 = make_employee(db, "E1", "n1@test.in")
        e2 = make_employee(db, "E2", "n2@test.in")
        db.add(L(first_name="x", email="x@test.in", owner_id=e1.id)); db.commit()
        # Within {e1, e2}, e2 has fewer leads → picked.
        assert next_owner_id(db, among={e1.id, e2.id}) == e2.id
        # Restricted to just e1, it's the only candidate.
        assert next_owner_id(db, among={e1.id}) == e1.id


class TestManualAddProfile:
    def test_webhook_accepts_team_size_and_website(self, client, db):
        # The manual "Add lead" form posts here; it can now carry the richer profile.
        r = client.post("/webhook/lead", json={
            "first_name": "Manual", "email": "manual@test.in", "phone": "9000000001",
            "types_of_business": "broker", "platform": "fb",
            "team_size": 18, "company_website": "manual.in",
        })
        assert r.status_code == 200
        lead = db.query(Lead).filter(Lead.email == "manual@test.in").first()
        assert lead.team_size == 18
        assert lead.company_website == "manual.in"


class TestTemplate:
    def test_template_download(self, client, db):
        as_user(make_employee(db))
        r = client.get("/leads/import-template")
        assert r.status_code == 200
        assert "Name,Email,Phone" in r.text
        assert "attachment" in r.headers.get("content-disposition", "")
