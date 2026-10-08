import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.demo import DEMO_TEXT
from app.main import create_app


def test_empty_dashboard(client):
    assert client.get("/api/health").json()["status"] == "ok"
    stats = client.get("/api/stats").json()
    assert stats["questions"] == stats["total_answered"] == stats["accuracy"] == 0
    assert client.get("/api/history").json() == []
    assert client.get("/api/wrongbook").json() == []
    assert client.get("/api/export").status_code == 409
    config = client.get("/api/config").json()
    assert config["remote_ready"] is False
    assert "api_key" not in config


def test_seed_idempotent_and_demo_generation(client, seeded):
    second = client.post("/api/demo/seed").json()
    assert second == seeded
    assert len(client.get("/api/questions").json()) == 10
    result = client.post(
        "/api/generate",
        json={
            "material_id": seeded["material"]["id"],
            "count": 3,
        },
    )
    assert result.status_code == 200
    assert len(result.json()["questions"]) == 3
    assert all(q["generator"] == "demo-curated" for q in result.json()["questions"])
    assert len(client.get("/api/questions").json()) == 10
    assert (
        client.post("/api/generate", json={"material_id": 1, "difficulty": "hard"}).status_code
        == 422
    )


def test_full_quiz_wrongbook_repractice(client, seeded):
    questions = seeded["questions"][:3]
    ids = [q["id"] for q in questions]
    quiz = client.post("/api/quizzes", json={"question_ids": ids}).json()
    assert not {"answer", "explanation", "source_quote"} & quiz["questions"][0].keys()
    assert client.get(f"/api/history/{quiz['id']}").status_code == 409
    # One correct, one wrong, one unanswered; unanswered is marked wrong.
    answers = {str(ids[0]): questions[0]["answer"], str(ids[1]): (questions[1]["answer"] + 1) % 4}
    result = client.post(f"/api/quizzes/{quiz['id']}/submit", json={"answers": answers}).json()
    assert result["score"] == 33.3 and result["correct"] == 1 and result["total"] == 3
    assert result["results"][2]["selected"] is None
    assert len(client.get("/api/wrongbook").json()) == 2
    assert len(client.get("/api/history").json()) == 1
    # Repeated submissions cannot change the recorded result or inflate stats/wrong counts.
    repeated = client.post(f"/api/quizzes/{quiz['id']}/submit", json={"answers": {}}).json()
    assert repeated == result
    stats = client.get("/api/stats").json()
    assert stats["total_answered"] == 3 and stats["wrong_count"] == 2
    assert all(w["wrong_count"] == 1 for w in client.get("/api/wrongbook").json())
    repeat = client.post("/api/quizzes", json={"question_ids": ids[1:], "mode": "wrongbook"}).json()
    corrected = {str(q["id"]): q["answer"] for q in questions[1:]}
    assert (
        client.post(f"/api/quizzes/{repeat['id']}/submit", json={"answers": corrected}).json()[
            "score"
        ]
        == 100
    )
    assert client.get("/api/stats").json()["wrong_count"] == 0
    assert all(w["mastered"] for w in client.get("/api/wrongbook").json())
    assert client.patch(f"/api/wrongbook/{ids[1]}", json={"mastered": False}).status_code == 200
    assert client.get("/api/stats").json()["wrong_count"] == 1
    assert client.get(f"/api/history/{repeat['id']}").json()["score"] == 100


@pytest.mark.parametrize("ids", [[], [1, 1], [-1], [True], list(range(1, 52))])
def test_bad_quiz_ids(client, seeded, ids):
    assert client.post("/api/quizzes", json={"question_ids": ids}).status_code == 422


def test_missing_and_wrongbook_ids(client, seeded):
    assert client.post("/api/quizzes", json={"question_ids": [999]}).status_code == 404
    assert (
        client.post("/api/quizzes", json={"question_ids": [1], "mode": "wrongbook"}).status_code
        == 422
    )
    assert client.get("/api/history/999").status_code == 404
    assert client.patch("/api/wrongbook/999", json={"mastered": True}).status_code == 404
    assert client.post("/api/quizzes/999/submit", json={"answers": {}}).status_code == 404


@pytest.mark.parametrize("answers", [{"999": 0}, {"1": 4}, {"1": -1}, {"1": True}, {"1": "0"}])
def test_invalid_answers_do_not_submit(client, seeded, answers):
    quiz = client.post("/api/quizzes", json={"question_ids": [1]}).json()
    assert (
        client.post(f"/api/quizzes/{quiz['id']}/submit", json={"answers": answers}).status_code
        == 422
    )
    assert client.get("/api/history").json() == []
    assert client.get("/api/stats").json()["total_answered"] == 0


def test_material_text_and_upload(client):
    payload = {
        "title": "基础资料",
        "course": "课程",
        "text": "本资料是原创文本。用于验证资料上传及数据持久化功能。",
    }
    created = client.post("/api/materials", json=payload)
    assert created.status_code == 201
    assert client.post("/api/materials", json=payload).json()["id"] == created.json()["id"]
    assert (
        client.post("/api/generate", json={"material_id": created.json()["id"]}).status_code == 422
    )
    upload = client.post(
        "/api/materials/upload",
        data={"title": "上传", "course": "课程"},
        files={"file": ("source.md", DEMO_TEXT.encode(), "text/markdown")},
    )
    assert upload.status_code == 201 and upload.json()["text"] == DEMO_TEXT
    assert len(client.get("/api/materials").json()) == 2
    assert client.get("/api/questions?material_id=999").json() == []


@pytest.mark.parametrize(
    "data",
    [
        {"title": "", "course": "x", "text": "x" * 20},
        {"title": "x", "course": "x", "text": "short"},
        {"title": "x", "course": "x", "text": "x" * 30001},
        {"title": "x", "course": "x", "text": "x" * 20 + "\x00"},
    ],
)
def test_material_bounds(client, data):
    assert client.post("/api/materials", json=data).status_code == 422
    assert client.get("/api/materials").json() == []


def test_export_import_roundtrip_and_dedup(client, seeded, tmp_path):
    export = client.get("/api/export")
    assert "attachment" in export.headers["content-disposition"]
    with TestClient(
        create_app(Settings(database_path=str(tmp_path / "other.db"))),
        headers={"X-Requested-With": "quiz-app"},
    ) as target:
        for _ in range(2):
            response = target.post("/api/import", files={"file": ("bank.json", export.content)})
            assert response.status_code == 200
        assert len(target.get("/api/materials").json()) == 1
        bank = target.get("/api/questions").json()
        assert len(bank) == 10 and all(q["generator"] == "imported" for q in bank)
        assert target.get("/api/export").json() == export.json()


@pytest.mark.parametrize(
    "change", ["source", "missing", "duplicate", "answer", "unknown", "format"]
)
def test_import_rejects_entire_invalid_bundle(client, seeded, change):
    bundle = client.get("/api/export").json()
    if change == "source":
        bundle["questions"][-1]["source_quote"] = "这句原文并不存在于资料中。"
    elif change == "missing":
        bundle["questions"][0]["material_id"] = 999
    elif change == "duplicate":
        bundle["materials"].append(bundle["materials"][0])
    elif change == "answer":
        bundle["questions"][0]["answer"] = True
    elif change == "unknown":
        bundle["admin"] = True
    else:
        bundle["format"] = "other"
    before = client.get("/api/stats").json()
    response = client.post("/api/import", files={"file": ("bad.json", json.dumps(bundle))})
    assert response.status_code == 422
    assert client.get("/api/stats").json() == before


def test_persistence_after_reopen(tmp_path):
    settings = Settings(database_path=str(tmp_path / "persist.db"))
    with TestClient(create_app(settings), headers={"X-Requested-With": "quiz-app"}) as first:
        first.post("/api/demo/seed")
        quiz = first.post("/api/quizzes", json={"question_ids": [1]}).json()
        first.post(f"/api/quizzes/{quiz['id']}/submit", json={"answers": {}})
    with TestClient(create_app(settings)) as second:
        assert second.get("/api/stats").json()["wrong_count"] == 1
        assert len(second.get("/api/history").json()) == 1
        assert len(second.get("/api/questions").json()) == 10


def test_invalid_unicode_is_rejected_without_server_error(client):
    payload = {"title": "bad", "course": "test", "text": "x" * 20 + "\ud800"}
    response = client.post(
        "/api/materials", content=json.dumps(payload), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert client.get("/api/materials").json() == []


def test_page_assets_and_schema_are_local(client):
    for path in ("/", "/static/app.js", "/static/style.css", "/openapi.json"):
        response = client.get(path)
        assert response.status_code == 200
        assert "script-src 'self'" in response.headers["content-security-policy"]
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
