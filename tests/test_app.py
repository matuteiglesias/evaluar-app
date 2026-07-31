import importlib
import re
import sys
from pathlib import Path

import pytest

USER = {"id_": "user-123", "name": "Test User", "email": "test@example.com"}
BASE_CONFIG = {
    "TESTING": True,
    "SECRET_KEY": "phase-0b-deterministic-secret",
    "FIREBASE_ENABLED": False,
    "SESSION_COOKIE_SECURE": False,
    "RATELIMIT_ENABLED": True,
    "ANSWER_RATE_LIMIT": "100 per minute",
    "FEEDBACK_RATE_LIMIT": "100 per minute",
    "TEACHER_HELP_RATE_LIMIT": "100 per minute",
}


class FakeDocument:
    def __init__(self):
        self.writes = []

    def set(self, value):
        self.writes.append(value)

    def get(self):
        return self

    def to_dict(self):
        return {"name": "Teacher"}


class FakeCollection:
    def __init__(self):
        self.documents = {}

    def document(self, identifier=None):
        identifier = identifier or f"generated-{len(self.documents)}"
        return self.documents.setdefault(identifier, FakeDocument())


class FakeDB:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection())


class FakeEvaluator:
    calls = []

    def evaluate(self, content, response):
        self.calls.append((content, response))
        return "safe fake evaluation"


@pytest.fixture
def app():
    from main import create_app

    app = create_app(BASE_CONFIG)
    app.extensions["firebase_db"] = FakeDB()
    app.extensions["evaluator"] = FakeEvaluator()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, user_id="user-123"):
    with client.session_transaction() as session:
        session["user"] = {**USER, "id_": user_id}


def csrf_token(client, path="/exercises/tda/101.tex"):
    response = client.get(path)
    match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
    assert match, response.data
    return match.group(1).decode()


def test_application_health_and_routes(app, client):
    assert client.get("/health").get_json() == {"status": "up"}
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/submit_answer" in rules
    assert "/request-teacher-time" in rules


def test_import_and_app_creation_do_not_open_network_connections(monkeypatch):
    def fail_network(*args, **kwargs):
        raise AssertionError("external network access attempted")

    socket = importlib.import_module("socket")
    monkeypatch.setattr(socket, "create_connection", fail_network)
    monkeypatch.setattr(socket.socket, "connect", fail_network)
    for name in list(sys.modules):
        if name == "main" or name.startswith(("routes.", "services.", "llm.")):
            sys.modules.pop(name, None)

    main = importlib.import_module("main")
    created_app = main.create_app(BASE_CONFIG)
    assert created_app.test_client().get("/health").status_code == 200


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/course"),
        ("get", "/get_courses"),
        ("get", "/get_exercises"),
        ("get", "/exercises/tda/101.tex"),
        ("post", "/submit_answer"),
        ("post", "/submit-feedback"),
        ("post", "/request-teacher-time"),
        ("get", "/confirmation"),
    ],
)
def test_every_protected_endpoint_rejects_anonymous_users(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code in {302, 400}


@pytest.mark.parametrize(
    "path",
    [
        "/get_exercises?course=..",
        "/get_exercises?course=../tda",
        "/get_exercises?course=%2e%2e%2ftda",
        "/get_exercises?course=/tmp",
        "/get_exercises?course=bad.course",
        "/get_exercises?course=unknown-course",
        "/exercises/tda/not-in-index.tex",
        "/exercises/tda/%2Fetc%2Fpasswd",
        "/exercises/tda/%2e%2e%2findex.csv",
        "/exercises/tda/nested%2f..%2f101.tex",
    ],
)
def test_invalid_course_and_exercise_paths_are_not_found(client, path):
    login(client)
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("path", ["/exercises/tda/101.tex", "/exercises/demo_course/202.tex"])
def test_valid_indexed_exercises_from_multiple_courses(client, path):
    login(client)
    response = client.get(path)
    assert response.status_code == 200
    assert b"csrf_token" in response.data


@pytest.mark.parametrize("path", ["/submit_answer", "/submit-feedback", "/request-teacher-time"])
def test_mutating_routes_reject_missing_and_invalid_csrf(client, path):
    login(client)
    assert client.post(path, data={}).status_code == 400
    assert client.post(path, data={"csrf_token": "invalid"}).status_code == 400


@pytest.mark.parametrize(
    ("config_name", "field", "path"),
    [
        ("MAX_ANSWER_LENGTH", "response", "/submit_answer"),
        ("MAX_FEEDBACK_LENGTH", "feedback", "/submit-feedback"),
        ("MAX_TEACHER_QUESTION_LENGTH", "question", "/request-teacher-time"),
    ],
)
def test_input_limits_accept_boundary_and_reject_overlong(
    app, client, monkeypatch, config_name, field, path
):
    app.config[config_name] = 5
    login(client)
    token = csrf_token(client)
    data = {"csrf_token": token, "exercise_id": "101", "course": "tda", field: "12345"}
    if path == "/submit-feedback":
        data["response_id"] = "response-boundary"
        with client.session_transaction() as state:
            state["current_ai_response"] = {
                "response_id": "response-boundary",
                "course": "tda",
                "exercise_id": "101",
                "evaluated_response": "fixed guidance",
            }
    monkeypatch.setattr("routes.teachers.get_teacher_loads", lambda: ({"teacher": 0}, 0))
    monkeypatch.setattr("routes.teachers.find_eligible_teacher", lambda *args: "teacher")
    assert client.post(path, data=data).status_code in {200, 302}

    data[field] = "123456"
    assert client.post(path, data=data).status_code == 400


@pytest.mark.parametrize(
    ("field", "path"),
    [
        ("response", "/submit_answer"),
        ("feedback", "/submit-feedback"),
        ("question", "/request-teacher-time"),
    ],
)
def test_whitespace_only_input_is_rejected(client, field, path):
    login(client)
    data = {"csrf_token": csrf_token(client), "exercise_id": "101", field: "  \n "}
    assert client.post(path, data=data).status_code == 400


def test_request_body_limit_returns_413(app, client):
    app.config["MAX_CONTENT_LENGTH"] = 32
    login(client)
    assert client.post("/submit_answer", data={"response": "x" * 100}).status_code == 413


def test_valid_answer_uses_fake_evaluator_and_firestore(app, client):
    login(client)
    FakeEvaluator.calls.clear()
    response = client.post(
        "/submit_answer",
        data={
            "csrf_token": csrf_token(client),
            "exercise_id": "101",
            "course": "tda",
            "response": " answer ",
        },
    )
    assert response.status_code == 200
    assert FakeEvaluator.calls[-1][1] == "answer"


def test_configured_answer_rate_limit_is_enforced(app, client):
    app.config["ANSWER_RATE_LIMIT"] = "1 per minute"
    login(client, "rate-answer-user")
    token = csrf_token(client)
    data = {"csrf_token": token, "exercise_id": "101", "response": "answer"}
    assert client.post("/submit_answer", data=data).status_code == 200
    assert client.post("/submit_answer", data=data).status_code == 429


@pytest.mark.parametrize(
    ("config_name", "path", "field"),
    [
        ("FEEDBACK_RATE_LIMIT", "/submit-feedback", "feedback"),
        ("TEACHER_HELP_RATE_LIMIT", "/request-teacher-time", "question"),
    ],
)
def test_other_authenticated_rate_limits_are_enforced(
    app, client, monkeypatch, config_name, path, field
):
    app.config[config_name] = "1 per minute"
    login(client, f"rate-{field}-user")
    monkeypatch.setattr("routes.teachers.get_teacher_loads", lambda: ({"teacher": 0}, 0))
    monkeypatch.setattr("routes.teachers.find_eligible_teacher", lambda *args: "teacher")
    data = {
        "csrf_token": csrf_token(client),
        "exercise_id": "101",
        "course": "tda",
        field: "valid input",
    }
    if path == "/submit-feedback":
        data["response_id"] = "response-rate"
        with client.session_transaction() as state:
            state["current_ai_response"] = {
                "response_id": "response-rate",
                "course": "tda",
                "exercise_id": "101",
                "evaluated_response": "fixed guidance",
            }
    assert client.post(path, data=data).status_code in {200, 302}
    assert client.post(path, data=data).status_code == 429


def test_login_rate_limit_uses_direct_remote_address(app, client, monkeypatch):
    app.config["LOGIN_RATE_LIMIT"] = "1 per minute"
    monkeypatch.setattr(
        "routes.auth.oauth.google.authorize_redirect",
        lambda **kwargs: ("oauth redirect", 302),
    )
    assert client.get("/login", environ_base={"REMOTE_ADDR": "192.0.2.10"}).status_code == 302
    assert client.get("/login", environ_base={"REMOTE_ADDR": "192.0.2.10"}).status_code == 429


def test_fake_teacher_ticket_is_created_without_name_error(app, client, monkeypatch):
    login(client)
    monkeypatch.setattr("routes.teachers.get_teacher_loads", lambda: ({"teacher": 0}, 0))
    monkeypatch.setattr("routes.teachers.find_eligible_teacher", lambda *args: "teacher")
    response = client.post(
        "/request-teacher-time",
        data={"csrf_token": csrf_token(client), "exercise_id": "101", "question": "Help"},
    )
    assert response.status_code == 302
    tickets = app.extensions["firebase_db"].collection("tickets").documents
    assert len(tickets) == 1


def test_exercise_rendering_sanitizes_repository_html(app, client, tmp_path):
    course = tmp_path / "malicious"
    course.mkdir()
    (course / "index.csv").write_text(
        "id,section,file,name,info\n1,1,1.tex,Safe,Safe\n", encoding="utf-8"
    )
    (course / "1.tex").write_text(
        r"""\emph{usable} $x < y$ \begin{enumerate}\item item\end{enumerate}
        <script>alert(1)</script><img src=x onerror=alert(2)>
        <svg onload=alert(3)><a href="javascript:alert(4)">x</a></svg>
        \href{javascript:alert(5)}{bad} <div><p><b malformed""",
        encoding="utf-8",
    )
    app.config["EXERCISES_ROOT"] = str(tmp_path)
    login(client, "safe-render-user")

    body = client.get("/exercises/malicious/1.tex").get_data(as_text=True)
    assert "<em>usable</em>" in body
    assert "<ol>" in body and "<li>" in body
    assert "$x &lt; y$" in body
    assert "<script" not in body
    assert "onerror" not in body and "onload" not in body
    assert "javascript:" not in body and "<svg" not in body
    assert "\\href" not in body and "＼href" in body


def test_model_markdown_is_sanitized_after_conversion(app, client):
    app.extensions["evaluator"].evaluate = lambda content, response: (
        """
**emphasis**

- list item

```python
print('code')
```

$x^2$ <script>alert(1)</script><img src=x onerror=alert(2)>
<svg onload=alert(3)></svg><a href="javascript:alert(4)">bad</a>
<div><p><b malformed
"""
    )
    login(client, "safe-model-user")
    response = client.post(
        "/submit_answer",
        data={
            "csrf_token": csrf_token(client),
            "exercise_id": "101",
            "course": "tda",
            "response": "student-controlled prompt",
        },
    )
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "<strong>emphasis</strong>" in body
    assert "<li>list item</li>" in body
    assert "<pre><code" in body and "print" in body
    assert "$x^2$" in body
    assert "<script" not in body and "<img" not in body and "<svg" not in body
    assert "onerror" not in body and "onload" not in body and "javascript:" not in body


def test_repository_metadata_is_only_inserted_with_text_content(app, client, tmp_path):
    course = tmp_path / "metadata"
    course.mkdir()
    payload = "<img src=x onerror=alert(1)><script>alert(2)</script>"
    (course / "index.csv").write_text(
        f'id,section,file,name,info\n1,1,1.tex,"{payload}","{payload}"\n', encoding="utf-8"
    )
    (course / "1.tex").write_text("Readable", encoding="utf-8")
    app.config["EXERCISES_ROOT"] = str(tmp_path)
    login(client, "metadata-user")
    assert client.get("/get_exercises?course=metadata").status_code == 200

    template = Path("templates/index.html").read_text(encoding="utf-8")
    assert "innerHTML" not in template
    assert "cell.textContent" in template
    assert "link.textContent" in template


def test_reflected_teacher_question_is_html_escaped(app, client, monkeypatch):
    login(client, "reflected-question-user")
    monkeypatch.setattr("routes.teachers.get_teacher_loads", lambda: ({"teacher": 0}, 0))
    monkeypatch.setattr("routes.teachers.find_eligible_teacher", lambda *args: "teacher")
    payload = "<img src=x onerror=alert(1)><script>alert(2)</script>"
    response = client.post(
        "/request-teacher-time",
        data={"csrf_token": csrf_token(client), "exercise_id": "101", "question": payload},
        follow_redirects=True,
    )
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "&lt;img" in body and "&lt;script&gt;" in body
    assert '<img src="x"' not in body and "<script>alert(2)</script>" not in body


def test_production_startup_fails_without_mandatory_configuration(monkeypatch):
    from main import create_app
    from services.settings import ConfigurationError

    for name in ("SECRET_KEY", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ConfigurationError) as error:
        create_app()
    message = str(error.value)
    assert "SECRET_KEY" in message
    assert "GOOGLE_CLIENT_ID" in message
    assert "GOOGLE_CLIENT_SECRET" in message
    assert "OPENAI_API_KEY" in message


def test_production_cookie_and_debug_defaults_are_fail_closed(monkeypatch):
    from main import create_app

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "Strong-production-session-secret-2026!A7")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-production-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-production-client-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "test-production-openai-key")
    app = create_app()
    assert app.debug is False
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["SESSION_COOKIE_SECURE"] is True


def test_openai_key_is_optional_only_when_ai_is_disabled(monkeypatch):
    from main import create_app

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "Strong-production-session-secret-2026!A7")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-production-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-production-client-secret")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AI_EVALUATION_ENABLED", "false")
    assert create_app().config["AI_EVALUATION_ENABLED"] is False


def test_test_startup_needs_no_live_credentials(monkeypatch):
    from main import create_app

    for name in (
        "SECRET_KEY",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "OPENAI_API_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ):
        monkeypatch.delenv(name, raising=False)
    test_app = create_app(BASE_CONFIG)
    assert test_app.test_client().get("/health").status_code == 200


class OAuthResponse:
    def __init__(self, data, status_error=None):
        self.data = data
        self.status_error = status_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        return self.data


def test_oauth_callback_uses_timeouts_and_handles_malformed_json(app, client, monkeypatch):
    import requests

    observed = {}

    def token(**kwargs):
        observed["token_timeout"] = kwargs["timeout"]
        return {"access_token": "test-token"}

    def userinfo(endpoint, **kwargs):
        observed["userinfo_timeout"] = kwargs["timeout"]
        return OAuthResponse(None)

    monkeypatch.setattr("routes.auth.oauth.google.authorize_access_token", token)
    monkeypatch.setattr("routes.auth.oauth.google.get", userinfo)
    response = client.get("/login/callback?code=test&state=test")
    assert response.status_code == 502
    assert observed == {"token_timeout": (3.05, 10.0), "userinfo_timeout": (3.05, 10.0)}

    monkeypatch.setattr(
        "routes.auth.oauth.google.get",
        lambda *args, **kwargs: OAuthResponse({}, requests.HTTPError("upstream")),
    )
    assert client.get("/login/callback?code=test&state=test").status_code == 502
