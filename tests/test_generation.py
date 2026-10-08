import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.demo import DEMO_TEXT, demo_questions
from app.generation import GenerationError, generate_remote, parse_model_content
from app.main import create_app


def payload():
    return {"questions": [q.model_dump() for q in demo_questions(2)]}


def test_parse_valid():
    assert len(parse_model_content(json.dumps(payload()), DEMO_TEXT, 2)) == 2


@pytest.mark.parametrize(
    "mutation",
    [
        "fence",
        "empty",
        "options",
        "duplicate_options",
        "boolean",
        "answer",
        "quote",
        "count",
        "extra",
        "duplicate",
        "difficulty",
    ],
)
def test_reject_malformed_model_output(mutation):
    data = payload()
    if mutation == "fence":
        content = "```json\n" + json.dumps(data) + "\n```"
    elif mutation == "empty":
        content = ""
    else:
        q = data["questions"][0]
        if mutation == "options":
            q["options"] = ["one", "two"]
        elif mutation == "duplicate_options":
            q["options"] = ["same"] * 4
        elif mutation == "boolean":
            q["answer"] = True
        elif mutation == "answer":
            q["answer"] = 4
        elif mutation == "quote":
            q["source_quote"] = "a fabricated unsupported quote"
        elif mutation == "count":
            data["questions"].pop()
        elif mutation == "extra":
            q["untrusted"] = "ignored?"
        elif mutation == "duplicate":
            data["questions"][1] = q
        else:
            q["difficulty"] = "expert"
        content = json.dumps(data)
    with pytest.raises(GenerationError):
        parse_model_content(content, DEMO_TEXT, 2)


def mock_client(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(
        "app.generation.httpx.Client",
        lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    )


def test_remote_adapter_request_and_response(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        body = json.loads(request.content)
        assert request.url == "https://api.deepseek.com/chat/completions"
        assert body["response_format"] == {"type": "json_object"}
        assert "不可信" in body["messages"][0]["content"]
        user = json.loads(body["messages"][1]["content"])
        assert user["untrusted_learning_material"] == DEMO_TEXT
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"content": json.dumps(payload())}}
                ]
            },
        )

    mock_client(monkeypatch, handler)
    result = generate_remote(
        Settings(api_mode="openai", api_key="fake-test-key"), DEMO_TEXT, 2, "easy"
    )
    assert len(result) == 2 and len(calls) == 1


@pytest.mark.parametrize(
    "failure", ["http", "truncated", "malformed", "redirect", "timeout", "oversize", "difficulty"]
)
def test_provider_failure_no_retry_or_secret_leak(monkeypatch, failure):
    calls = []

    def handler(request):
        calls.append(request)
        if failure == "http":
            return httpx.Response(401, text="fake-test-secret")
        if failure == "redirect":
            return httpx.Response(307, headers={"Location": "https://evil.example"})
        if failure == "timeout":
            raise httpx.ReadTimeout("fake-test-secret")
        if failure == "oversize":
            return httpx.Response(200, content=b"x" * 200001)
        if failure == "malformed":
            return httpx.Response(200, json={"unknown": "fake-test-secret"})
        data = payload()
        if failure == "difficulty":
            data["questions"][0]["difficulty"] = "hard"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length" if failure == "truncated" else "stop",
                        "message": {"content": json.dumps(data)},
                    }
                ]
            },
        )

    mock_client(monkeypatch, handler)
    with pytest.raises(GenerationError) as error:
        generate_remote(Settings(api_key="fake-test-secret"), DEMO_TEXT, 2, "easy")
    assert "fake-test-secret" not in str(error.value)
    assert len(calls) == 1


def test_api_requires_enabled_mode_and_confirmation(client, seeded, tmp_path, monkeypatch):
    assert (
        client.post(
            "/api/generate", json={"material_id": 1, "mode": "openai", "confirm_send": True}
        ).status_code
        == 409
    )
    settings = Settings(
        database_path=str(tmp_path / "remote.db"), api_mode="openai", api_key="fake-test-key"
    )
    with TestClient(create_app(settings), headers={"X-Requested-With": "quiz-app"}) as remote:
        remote.post("/api/demo/seed")
        assert (
            remote.post("/api/generate", json={"material_id": 1, "mode": "openai"}).status_code
            == 400
        )
        calls = []

        def generated(*args):
            calls.append(args)
            return demo_questions(2)

        monkeypatch.setattr("app.main.generate_remote", generated)
        response = remote.post(
            "/api/generate",
            json={"material_id": 1, "mode": "openai", "count": 2, "confirm_send": True},
        )
        assert response.status_code == 200 and len(calls) == 1
        assert "fake-test-key" not in remote.get("/api/config").text

        def failed(*args):
            raise GenerationError("模拟校验失败")

        monkeypatch.setattr("app.main.generate_remote", failed)
        response = remote.post(
            "/api/generate", json={"material_id": 1, "mode": "openai", "confirm_send": True}
        )
        assert response.status_code == 502
        with remote.app.state.db.connect() as con:
            assert (
                con.execute("SELECT status FROM generation_runs ORDER BY id DESC").fetchone()[0]
                == "failed"
            )


@pytest.mark.parametrize(
    "url",
    [
        "http://api.example.com",
        "https://user:secret@example.com",
        "https://example.com?q=secret",
        "https://example.com#secret",
        "not-a-url",
    ],
)
def test_invalid_provider_config(url):
    with pytest.raises(ValueError):
        Settings(base_url=url).validate()
