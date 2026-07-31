import csv
from datetime import datetime, timezone
import re

import pytest

from main import create_app
from services.identity import AuthenticatedIdentity


class FakeIdentityProvider:
    def __init__(self):
        self.redirect_uri = None

    def begin(self, redirect_uri):
        self.redirect_uri = redirect_uri
        return "fake identity redirect", 302

    def complete(self, timeout):
        assert timeout == (3.05, 10.0)
        return AuthenticatedIdentity("student-1", "student@example.test", "Student")


class FakePersistence:
    def __init__(self):
        self.interactions = {}
        self.feedback = {}
        self.teacher_packets = {}
        self.fail_interactions = False

    def save_interaction(self, identifier, record):
        if self.fail_interactions:
            raise RuntimeError("simulated persistence outage")
        self.interactions[identifier] = record

    def save_feedback(self, identifier, record):
        self.feedback[identifier] = record

    def save_teacher_packet(self, identifier, record):
        self.teacher_packets[identifier] = record


class FakeTutor:
    def __init__(self):
        self.calls = []

    def guide(self, course, exercise_id, content, question):
        self.calls.append((course, exercise_id, content, question))
        return f"Guidance for {course}:{exercise_id}"


class DeterministicIds:
    def __init__(self):
        self.counts = {}

    def __call__(self, kind, identity):
        self.counts[kind] = self.counts.get(kind, 0) + 1
        return f"{kind}-{self.counts[kind]}"


def write_course(root, slug, rows):
    course = root / slug
    course.mkdir(parents=True)
    with (course / "index.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "section", "file", "name", "info"])
        writer.writeheader()
        for identifier, section, content in rows:
            writer.writerow(
                {
                    "id": identifier,
                    "section": section,
                    "file": f"{identifier}.tex",
                    "name": f"Exercise {identifier}",
                    "info": "Characterization fixture",
                }
            )
            (course / f"{identifier}.tex").write_text(content, encoding="utf-8")


@pytest.fixture
def journey_app(tmp_path):
    exercises = tmp_path / "exercises"
    write_course(
        exercises,
        "alpha",
        [("101", "one", "Alpha immutable content\n% FIGURA"), ("102", "two", "Second")],
    )
    write_course(exercises, "beta", [("101", "other", "Different course content")])
    identity = FakeIdentityProvider()
    persistence = FakePersistence()
    tutor = FakeTutor()
    fixed_time = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "journey-contract-secret",
            "SESSION_COOKIE_SECURE": False,
            "FIREBASE_ENABLED": False,
            "RATELIMIT_ENABLED": False,
            "EXERCISES_ROOT": str(exercises),
        },
        adapters={
            "identity_provider": identity,
            "persistence": persistence,
            "tutor": tutor,
            "clock": lambda: fixed_time,
            "id_generator": DeterministicIds(),
        },
    )
    app.testing_adapters = (identity, persistence, tutor, fixed_time)
    return app


@pytest.fixture
def journey_client(journey_app):
    return journey_app.test_client()


def authenticate(client):
    with client.session_transaction() as state:
        state["user"] = {
            "id_": "student-1",
            "name": "Student",
            "email": "student@example.test",
        }


def token_from(response):
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match
    return match.group(1)


def hidden(response, name):
    match = re.search(
        rf'name="{re.escape(name)}"(?: id="[^"]+")? value="([^"]+)"',
        response.get_data(as_text=True),
    )
    assert match
    return match.group(1)


def exercise_form(client, course="alpha", exercise_id="101"):
    page = client.get(f"/exercises/{course}/{exercise_id}.tex")
    assert page.status_code == 200
    return token_from(page)


def ask(client, course="alpha", exercise_id="101"):
    return client.post(
        "/submit_answer",
        data={
            "csrf_token": exercise_form(client, course, exercise_id),
            "course": course,
            "exercise_id": exercise_id,
            "response": "Please give one hint",
        },
    )


def test_journey_authenticate_and_choose_course(journey_app, journey_client):
    identity, _, _, _ = journey_app.testing_adapters
    assert journey_client.get("/login").status_code == 302
    assert identity.redirect_uri.endswith("/login/callback")
    assert journey_client.get("/login/callback").status_code == 302
    assert journey_client.get("/get_courses").get_json() == ["alpha", "beta"]
    selected = journey_client.get("/course?course=alpha")
    assert selected.status_code == 200
    assert b"Lista de Ejercicios" in selected.data


def test_journey_browse_course_sections_and_exact_exercise(journey_client):
    authenticate(journey_client)
    rows = journey_client.get("/get_exercises?course=alpha").get_json()
    assert [(row["course"], row["id"], row["section"]) for row in rows] == [
        ("alpha", "101", "one"),
        ("alpha", "102", "two"),
    ]
    page = journey_client.get("/exercises/alpha/101.tex")
    assert b"Alpha immutable content" in page.data
    assert b"/tikzpics/101.png" in page.data
    assert journey_client.get("/exercises/beta/101.tex").status_code == 200


def test_journey_ai_guidance_uses_scoped_content_and_persists(journey_app, journey_client):
    authenticate(journey_client)
    _, persistence, tutor, fixed_time = journey_app.testing_adapters
    response = ask(journey_client)
    assert response.status_code == 200
    assert tutor.calls == [
        ("alpha", "101", "Alpha immutable content\n% FIGURA", "Please give one hint")
    ]
    assert persistence.interactions["response-1"]["course"] == "alpha"
    assert persistence.interactions["response-1"]["timestamp"] == fixed_time
    assert b"Guidance for alpha:101" in response.data

    persistence.fail_interactions = True
    failed = ask(journey_client, "alpha", "102")
    assert failed.status_code == 503
    assert b"could not be recorded" in failed.data


def test_journey_feedback_is_bound_to_one_response(journey_app, journey_client):
    authenticate(journey_client)
    _, persistence, _, fixed_time = journey_app.testing_adapters
    guidance = ask(journey_client)
    response_id = hidden(guidance, "response_id")
    csrf = token_from(guidance)
    mismatch = journey_client.post(
        "/submit-feedback",
        data={
            "csrf_token": csrf,
            "course": "beta",
            "exercise_id": "101",
            "response_id": response_id,
            "feedback": "useful",
        },
    )
    assert mismatch.status_code == 409
    assert not persistence.feedback

    payload = {
        "csrf_token": csrf,
        "course": "alpha",
        "exercise_id": "101",
        "response_id": response_id,
        "feedback": "useful",
    }
    assert journey_client.post("/submit-feedback", data=payload).status_code == 200
    record = persistence.feedback["feedback-1"]
    assert (record["responseId"], record["course"], record["exerciseId"]) == (
        "response-1",
        "alpha",
        "101",
    )
    assert record["timestamp"] == fixed_time
    assert journey_client.post("/submit-feedback", data=payload).status_code == 409


def test_journey_generic_teacher_packet_has_no_teacher_assignment(journey_app, journey_client):
    authenticate(journey_client)
    _, persistence, _, fixed_time = journey_app.testing_adapters
    response = journey_client.post(
        "/request-teacher-time",
        data={
            "csrf_token": exercise_form(journey_client),
            "course": "alpha",
            "exercise_id": "101",
            "question": "Please discuss the first step",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"teacher-packet-1" in response.data
    assert b"alpha:101" in response.data
    assert list(persistence.teacher_packets) == ["teacher-packet-1"]
    packet = persistence.teacher_packets["teacher-packet-1"]
    assert packet["assignment"] == "unassigned"
    assert "teacherId" not in packet
    assert packet["timestamp"] == fixed_time
