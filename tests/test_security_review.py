"""Independent adversarial regression tests; all remote responses are simulated."""

import json
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
)

from app import generation, materials
from app.config import Settings
from app.demo import DEMO_TEXT
from app.generation import GenerationError, generate_remote
from app.main import create_app
from app.materials import MaterialError, extract_text

HEADERS = {"X-Requested-With": "quiz-app"}


@pytest.fixture
def review_client(tmp_path):
    settings = Settings(database_path=str(tmp_path / "review.db"))
    with TestClient(create_app(settings)) as client:
        yield client


def seed(client):
    response = client.post("/api/demo/seed", headers=HEADERS)
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "http://testserver"},
        {**HEADERS, "Origin": "https://untrusted.example"},
        {**HEADERS, "Origin": "null"},
        {**HEADERS, "Origin": "http://testserver:9000"},
        {**HEADERS, "Origin": "http://testserver", "Sec-Fetch-Site": "cross-site"},
    ],
)
def test_cross_site_mutations_rejected(review_client, headers):
    response = review_client.post("/api/demo/seed", headers=headers)
    assert response.status_code == 403
    assert review_client.get("/api/stats").json()["materials"] == 0


def test_same_origin_mutation_allowed(review_client):
    response = review_client.post(
        "/api/demo/seed", headers={**HEADERS, "Origin": "http://testserver"}
    )
    assert response.status_code == 200


def test_untrusted_host_and_cors_preflight_rejected(review_client):
    assert review_client.get("/api/materials", headers={"Host": "evil.example"}).status_code == 400
    response = review_client.options(
        "/api/demo/seed",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Requested-With",
        },
    )
    assert "access-control-allow-origin" not in response.headers
    assert review_client.get("/api/stats").json()["materials"] == 0


def test_chunked_body_is_bounded_without_content_length(review_client):
    def chunks():
        for _ in range(7):
            yield b"x" * (1024 * 1024)

    response = review_client.post("/api/materials", headers=HEADERS, content=chunks())
    assert response.status_code == 413
    assert review_client.get("/api/stats").json()["materials"] == 0


def test_security_headers_and_private_error_redaction(review_client):
    response = review_client.get("/api/config")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
    assert "script-src 'self'" in response.headers["content-security-policy"]
    private_text = "PRIVATE-MATERIAL-DO-NOT-ECHO"
    response = review_client.post(
        "/api/materials",
        json={"title": "", "course": "test", "text": private_text},
        headers=HEADERS,
    )
    assert response.status_code == 422
    assert private_text not in response.text


def test_demo_never_calls_remote_even_when_explicitly_requested(review_client, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("A disabled remote adapter must never be invoked")

    monkeypatch.setattr("app.main.generate_remote", forbidden)
    result = seed(review_client)
    material_id = result["material"]["id"]
    response = review_client.post(
        "/api/generate", json={"material_id": material_id, "count": 2}, headers=HEADERS
    )
    assert response.status_code == 200
    response = review_client.post(
        "/api/generate",
        json={"material_id": material_id, "mode": "openai", "confirm_send": True},
        headers=HEADERS,
    )
    assert response.status_code == 409


def test_remote_requires_consent_and_key_is_never_returned(tmp_path, monkeypatch):
    secret = "FAKE-UNIT-TEST-SECRET-DO-NOT-ECHO"
    settings = Settings(
        database_path=str(tmp_path / "consent.db"), api_mode="openai", api_key=secret
    )

    def forbidden(*_args, **_kwargs):
        pytest.fail("No consent was supplied; remote calls are forbidden")

    monkeypatch.setattr("app.main.generate_remote", forbidden)
    with TestClient(create_app(settings)) as client:
        material_id = seed(client)["material"]["id"]
        assert secret not in client.get("/api/config").text
        assert secret not in client.get("/").text
        response = client.post(
            "/api/generate",
            json={"material_id": material_id, "mode": "openai"},
            headers=HEADERS,
        )
        assert response.status_code == 400
        assert secret not in response.text


def test_concurrent_submit_grades_once(review_client):
    questions = seed(review_client)["questions"][:3]
    quiz = review_client.post(
        "/api/quizzes", json={"question_ids": [q["id"] for q in questions]}, headers=HEADERS
    ).json()
    assert all(not {"answer", "source_quote", "explanation"} & set(q) for q in quiz["questions"])
    assert review_client.get(f"/api/history/{quiz['id']}").status_code == 409
    answers = {str(q["id"]): (q["answer"] + 1) % 4 for q in questions}

    def submit():
        return review_client.post(
            f"/api/quizzes/{quiz['id']}/submit", json={"answers": answers}, headers=HEADERS
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(lambda _: submit(), range(12)))
    assert all(response.status_code == 200 for response in responses)
    assert all(response.json() == responses[0].json() for response in responses)
    assert responses[0].json()["score"] == 0
    stats = review_client.get("/api/stats").json()
    assert stats["quiz_count"] == 1
    assert stats["total_answered"] == 3
    assert all(entry["wrong_count"] == 1 for entry in review_client.get("/api/wrongbook").json())


def test_invalid_import_is_atomic(review_client):
    original = seed(review_client)
    before = review_client.get("/api/stats").json()
    bundle = review_client.get("/api/export").json()
    new_material = {
        "id": 100,
        "title": "Must not be saved",
        "course": "Review",
        "text": "A different source text that is long enough.",
    }
    bundle["materials"].append(new_material)
    bundle["questions"][0]["source_quote"] = "A fabricated quotation absent from the source"
    response = review_client.post(
        "/api/import", files={"file": ("bank.json", json.dumps(bundle))}, headers=HEADERS
    )
    assert response.status_code == 422
    assert review_client.get("/api/stats").json() == before
    assert review_client.get("/api/materials").json() == [original["material"]]


def fake_transport(monkeypatch, handler):
    original_client = httpx.Client

    def client_factory(*args, **kwargs):
        assert kwargs.get("trust_env") is False
        assert not kwargs.get("follow_redirects", False)
        return original_client(*args, **kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(generation.httpx, "Client", client_factory)


@pytest.mark.parametrize(
    "envelope",
    [
        None,
        [],
        {},
        {"choices": None},
        {"choices": []},
        {"choices": [None]},
        {"choices": ["bad-choice"]},
        {"choices": [{"finish_reason": "stop", "message": None}]},
        {"choices": [{"finish_reason": "stop", "message": {"content": None}}]},
    ],
)
def test_malformed_provider_envelope_is_sanitized(monkeypatch, envelope):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=envelope)

    fake_transport(monkeypatch, handler)
    with pytest.raises(GenerationError):
        generate_remote(Settings(api_key="FAKE-UNIT-TEST-SECRET"), DEMO_TEXT, 1, "easy")
    assert len(calls) == 1


@pytest.mark.parametrize("status", [301, 302, 307, 400, 401, 429, 500, 503])
def test_provider_errors_are_redacted_without_retries_or_redirects(monkeypatch, status):
    private_body = "PRIVATE-PROVIDER-ERROR-AND-SECRET"
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status, text=private_body, headers={"Location": "https://untrusted.example"}
        )

    fake_transport(monkeypatch, handler)
    with pytest.raises(GenerationError) as error:
        generate_remote(Settings(api_key="FAKE-UNIT-TEST-SECRET"), DEMO_TEXT, 1, "easy")
    assert private_body not in str(error.value)
    assert "FAKE-UNIT-TEST-SECRET" not in str(error.value)
    assert len(calls) == 1


def test_oversized_provider_response_rejected(monkeypatch):
    fake_transport(monkeypatch, lambda _: httpx.Response(200, content=b"x" * 200_001))
    with pytest.raises(GenerationError, match="响应过大"):
        generate_remote(Settings(api_key="FAKE-UNIT-TEST-SECRET"), DEMO_TEXT, 1, "easy")


def oversized_nested_form_pdf():
    """A <3 KB file with a >2 MB decoded form bypassed the original page guard."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    resources = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    form = DecodedStreamObject()
    form.set_data(
        b" " * 2_000_100
        + b"BT /F1 12 Tf 72 720 Td (This is sufficiently long harmless example text.) Tj ET"
    )
    form.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Form"),
            NameObject("/BBox"): ArrayObject(
                [NumberObject(0), NumberObject(0), NumberObject(612), NumberObject(792)]
            ),
            NameObject("/Resources"): resources,
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/XObject"): DictionaryObject(
                {NameObject("/Fm0"): writer._add_object(form.flate_encode())}
            )
        }
    )
    content = DecodedStreamObject()
    content.set_data(b"/Fm0 Do")
    page[NameObject("/Contents")] = writer._add_object(content)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_pdf_nested_form_cannot_bypass_decoded_size_guard():
    content = oversized_nested_form_pdf()
    assert len(content) < 3000
    with pytest.raises(MaterialError):
        extract_text("nested.pdf", content, Settings())


@pytest.mark.parametrize("format_name", ["quiz-study-v0", "", None])
def test_import_unknown_version_is_rejected_without_changes(review_client, format_name):
    seed(review_client)
    original = review_client.get("/api/export").json()
    bundle = {**original, "format": format_name}
    response = review_client.post(
        "/api/import", files={"file": ("bank.json", json.dumps(bundle))}, headers=HEADERS
    )
    assert response.status_code == 422
    assert review_client.get("/api/export").json() == original


def test_api_rejects_client_supplied_score_and_non_integer_answers(review_client):
    question = seed(review_client)["questions"][0]
    quiz = review_client.post(
        "/api/quizzes", json={"question_ids": [question["id"]]}, headers=HEADERS
    ).json()
    for payload in (
        {"answers": {str(question["id"]): True}},
        {"answers": {str(question["id"]): "0"}},
        {"answers": {str(question["id"]): 0.0}},
        {"answers": {str(question["id"]): 4}},
        {"answers": {str(question["id"]): 0}, "score": 100},
    ):
        response = review_client.post(
            f"/api/quizzes/{quiz['id']}/submit", json=payload, headers=HEADERS
        )
        assert response.status_code == 422
    assert review_client.get("/api/stats").json()["quiz_count"] == 0
    assert review_client.get("/api/wrongbook").json() == []


def test_valid_quote_does_not_prove_answer_correctness():
    """The local gate is structural, not a semantic correctness oracle."""
    question = {
        "stem": "Which statement is actually supported by the source?",
        "options": ["An unsupported answer", "Another claim", "Third claim", "Fourth claim"],
        "answer": 0,
        "explanation": "An unsupported explanation still needs human review.",
        "source_quote": DEMO_TEXT[:30],
        "knowledge_point": "Human review boundary",
        "difficulty": "easy",
    }
    content = json.dumps({"questions": [question]}, ensure_ascii=False)
    assert len(generation.parse_model_content(content, DEMO_TEXT, 1)) == 1


@pytest.mark.parametrize("count,text_size", [(101, 20), (60, 30_000)])
def test_export_rejects_banks_that_cannot_be_reimported(review_client, count, text_size):
    with review_client.app.state.db.connect(write=True) as connection:
        connection.executemany(
            "INSERT INTO materials(title,course,text,content_hash,created_at) VALUES(?,?,?,?,?)",
            [
                (f"Material {index}", "Review", "学" * text_size, str(index), "2026-01-01")
                for index in range(count)
            ],
        )
    response = review_client.get("/api/export")
    assert response.status_code == 409
    assert "备份" in response.json()["detail"]
    assert review_client.get("/api/stats").json()["materials"] == count


def test_export_rejects_more_than_500_questions(review_client):
    first_question = seed(review_client)["questions"][0]["id"]
    with review_client.app.state.db.connect(write=True) as connection:
        for index in range(491):
            connection.execute(
                "INSERT INTO questions(material_id,stem,options,answer,explanation,source_quote,"
                "knowledge_point,difficulty,generator,fingerprint,created_at) "
                "SELECT material_id,stem,options,answer,explanation,source_quote,"
                "knowledge_point,difficulty,generator,?,created_at FROM questions WHERE id=?",
                (f"independent-security-fixture-{index}", first_question),
            )
    assert review_client.get("/api/stats").json()["questions"] == 501
    response = review_client.get("/api/export")
    assert response.status_code == 409
    assert "备份" in response.json()["detail"]


def test_pdf_timeout_cleans_up_worker_and_pipe(monkeypatch):
    receiver, sender, process, context = Mock(), Mock(), Mock(), Mock()
    receiver.poll.return_value = False
    process.pid = 123  # A mock only; this test never signals a real process.
    process.is_alive.return_value = True
    context.Pipe.return_value = receiver, sender
    context.Process.return_value = process
    monkeypatch.setattr(materials.multiprocessing, "get_context", lambda _: context)
    with pytest.raises(MaterialError, match="超时"):
        materials._bounded_pdf(b"synthetic-timeout", Settings())
    process.start.assert_called_once()
    receiver.poll.assert_called_once_with(12)
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert process.join.call_count == 2
    receiver.close.assert_called_once()
    assert sender.close.call_count >= 1


def test_pdf_worker_eof_becomes_sanitized_material_error(monkeypatch):
    receiver, sender, process, context = Mock(), Mock(), Mock(), Mock()
    receiver.poll.return_value = True
    receiver.recv.side_effect = EOFError("untrusted parser internals")
    process.pid = 123
    process.is_alive.return_value = False
    context.Pipe.return_value = receiver, sender
    context.Process.return_value = process
    monkeypatch.setattr(materials.multiprocessing, "get_context", lambda _: context)
    with pytest.raises(MaterialError) as error:
        materials._bounded_pdf(b"synthetic-worker-crash", Settings())
    assert "untrusted parser internals" not in str(error.value)
    process.join.assert_called_once()
    receiver.close.assert_called_once()
