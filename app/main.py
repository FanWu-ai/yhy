"""Local, single-user teaching application. Run bound to 127.0.0.1 only."""

import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from starlette.datastructures import Headers
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import ROOT, Settings, load_settings
from app.database import Database
from app.demo import DEMO_TEXT, demo_questions
from app.generation import GenerationError, generate_remote, validate_questions
from app.materials import MaterialError, extract_text
from app.schemas import (
    GenerateInput,
    ImportBundle,
    MasteredInput,
    MaterialInput,
    QuestionInput,
    QuizInput,
    SubmitInput,
)


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def question_dict(row) -> dict:
    result = dict(row)
    result["options"] = json.loads(result["options"])
    result.pop("fingerprint", None)
    return result


def get_material(con, material_id: int) -> dict:
    row = con.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "资料不存在")
    result = dict(row)
    result.pop("content_hash", None)
    return result


def save_material(con, item: MaterialInput, filename: str = "") -> dict:
    content_hash = digest(item.text)
    existing = con.execute(
        "SELECT id FROM materials WHERE content_hash = ? AND title = ? AND course = ?",
        (content_hash, item.title, item.course),
    ).fetchone()
    if existing:
        return get_material(con, existing["id"])
    cursor = con.execute(
        "INSERT INTO materials(title,course,filename,text,content_hash,created_at) "
        "VALUES(?,?,?,?,?,?)",
        (item.title, item.course, filename, item.text, content_hash, now()),
    )
    return get_material(con, cursor.lastrowid)


def save_questions(con, material_id: int, questions: list[QuestionInput], generator: str) -> list:
    saved = []
    for q in questions:
        fingerprint = digest(str(material_id) + json.dumps(q.model_dump(), sort_keys=True))
        con.execute(
            "INSERT OR IGNORE INTO questions(material_id,stem,options,answer,explanation,"
            "source_quote,knowledge_point,difficulty,generator,fingerprint,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                material_id,
                q.stem,
                json.dumps(q.options, ensure_ascii=False),
                q.answer,
                q.explanation,
                q.source_quote,
                q.knowledge_point,
                q.difficulty,
                generator,
                fingerprint,
                now(),
            ),
        )
        saved.append(
            question_dict(
                con.execute(
                    "SELECT * FROM questions WHERE fingerprint = ?", (fingerprint,)
                ).fetchone()
            )
        )
    return saved


def quiz_result(con, quiz_id: int) -> dict:
    quiz = con.execute("SELECT * FROM quiz_sessions WHERE id = ?", (quiz_id,)).fetchone()
    if quiz is None:
        raise HTTPException(404, "练习不存在")
    if quiz["submitted_at"] is None:
        raise HTTPException(409, "练习尚未提交，暂不能查看答案")
    results = []
    # Preserve the requested order, rather than relying on a join's unspecified order.
    for question_id in json.loads(quiz["question_ids"]):
        row = con.execute(
            "SELECT q.*,a.selected,a.is_correct FROM questions q JOIN quiz_answers a "
            "ON q.id=a.question_id WHERE a.quiz_id=? AND q.id=?",
            (quiz_id, question_id),
        ).fetchone()
        result = question_dict(row)
        result["question_id"] = result.pop("id")
        result["is_correct"] = bool(result["is_correct"])
        results.append(result)
    return {
        "id": quiz_id,
        "score": quiz["score"],
        "correct": quiz["correct"],
        "total": quiz["total"],
        "mode": quiz["mode"],
        "results": results,
        "created_at": quiz["created_at"],
        "submitted_at": quiz["submitted_at"],
    }


class LocalRequestGuard:
    """Custom headers + Origin checks block drive-by requests from other websites.

    This is not authentication. The app must remain bound to loopback.
    All mutation bodies are bounded even when Content-Length is absent.
    """

    def __init__(self, app, limit: int = 6 * 1024 * 1024):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        if scope["method"] in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = headers.get("origin")
            expected_origin = f"{scope['scheme']}://{headers.get('host', '')}"
            if (
                headers.get("x-requested-with") != "quiz-app"
                or (origin is not None and origin != expected_origin)
                or headers.get("sec-fetch-site") == "cross-site"
            ):
                return await JSONResponse(
                    {"detail": "仅接受本地页面的同源操作请求"}, status_code=403
                )(scope, receive, send)
            content = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                content.extend(message.get("body", b""))
                if len(content) > self.limit:
                    return await JSONResponse({"detail": "请求过大（最大 6 MB）"}, status_code=413)(
                        scope, receive, send
                    )
                if not message.get("more_body", False):
                    break
            sent = False
            original_receive = receive

            async def bounded_receive():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": bytes(content), "more_body": False}
                return await original_receive()

            receive = bounded_receive

        async def secure_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cache-control", b"no-store"),
                    (
                        b"content-security-policy",
                        b"default-src 'self'; script-src 'self'; "
                        b"style-src 'self'; img-src 'self' data:; connect-src 'self'; "
                        b"frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
                    ),
                ]
            await send(message)

        await self.app(scope, receive, secure_send)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    settings.validate()
    db = Database(settings.database_path)
    app = FastAPI(title="智能出题与错题管理系统", version="1.0.0", docs_url=None, redoc_url=None)
    app.state.db = db
    app.state.settings = settings
    generation_lock = threading.Lock()
    app.add_middleware(LocalRequestGuard)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"]
    )
    templates = Jinja2Templates(directory=str(ROOT / "app" / "templates"))
    (ROOT / "app" / "static").mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(ROOT / "app" / "static")), name="static")

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _exc):
        # Pydantic's default response includes original values; avoid echoing private content.
        return JSONResponse(
            {"detail": "输入格式不正确，请检查必填字段、长度和数值范围"}, status_code=422
        )

    @app.get("/")
    def home(request: Request):
        return templates.TemplateResponse(request=request, name="index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "1.0.0"}

    @app.get("/api/config")
    def config():
        return {
            "mode": settings.api_mode,
            "model": settings.model,
            "remote_ready": settings.remote_ready,
            "provider": urlparse(settings.base_url).hostname,
            "base_url": settings.base_url,
            "upload_limit_mb": 5,
        }

    @app.get("/api/materials")
    def materials():
        with db.connect() as con:
            return [
                get_material(con, r["id"])
                for r in con.execute("SELECT id FROM materials ORDER BY id DESC").fetchall()
            ]

    @app.post("/api/materials", status_code=201)
    def add_material(item: MaterialInput):
        with db.connect(write=True) as con:
            return save_material(con, item)

    @app.post("/api/materials/upload", status_code=201)
    async def upload_material(
        file: Annotated[UploadFile, File()],
        title: Annotated[str, Form()],
        course: Annotated[str, Form()],
    ):
        try:
            content = await file.read(settings.upload_limit_bytes + 1)
            text = extract_text(file.filename or "", content, settings)
            item = MaterialInput(title=title, course=course, text=text)
        except (MaterialError, ValidationError) as exc:
            message = (
                str(exc) if isinstance(exc, MaterialError) else "标题、课程名称或内容长度不正确"
            )
            raise HTTPException(422, message) from None
        finally:
            await file.close()
        with db.connect(write=True) as con:
            # Only keep a display name, never use the provided name as a filesystem path.
            return save_material(con, item, Path(file.filename or "").name[:200])

    @app.post("/api/demo/seed")
    def seed_demo():
        with db.connect(write=True) as con:
            material = save_material(
                con,
                MaterialInput(
                    title="Python 基础 · 原创演示资料", course="Python 程序设计", text=DEMO_TEXT
                ),
                "python_basics.md",
            )
            questions = save_questions(con, material["id"], demo_questions(10), "demo-curated")
            return {"material": material, "questions": questions}

    @app.get("/api/questions")
    def questions(material_id: int | None = None):
        with db.connect() as con:
            if material_id is None:
                rows = con.execute("SELECT * FROM questions ORDER BY id DESC").fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM questions WHERE material_id=? ORDER BY id DESC", (material_id,)
                ).fetchall()
            return [question_dict(row) for row in rows]

    @app.post("/api/generate")
    def generate(item: GenerateInput):
        with db.connect() as con:
            material = get_material(con, item.material_id)
        if item.mode == "demo":
            if material["text"] != DEMO_TEXT:
                raise HTTPException(
                    422, "离线模式只支持内置原创 Python 资料，请载入演示；其他资料需配置真实 API"
                )
            if item.difficulty != "easy":
                raise HTTPException(422, "离线演示题均为基础难度，不模拟中等或困难题")
            generated = demo_questions(item.count)
            note = "原创固定演示题，不是大模型生成；重复题自动复用。"
        else:
            if not settings.remote_ready:
                raise HTTPException(409, "真实 API 尚未启用，请在本机 .env 中配置后重启")
            if not item.confirm_send:
                raise HTTPException(400, "请确认将所选资料发送给已配置服务商，并知悉可能产生费用")
            if not generation_lock.acquire(blocking=False):
                raise HTTPException(429, "已有一个出题请求进行中，请勿重复提交")
            try:
                generated = generate_remote(settings, material["text"], item.count, item.difficulty)
            except GenerationError as exc:
                with db.connect(write=True) as con:
                    con.execute(
                        "INSERT INTO "
                        "generation_runs(material_id,mode,requested_count,status,created_at) "
                        "VALUES(?,?,?,?,?)",
                        (item.material_id, item.mode, item.count, "failed", now()),
                    )
                raise HTTPException(502, str(exc)) from None
            finally:
                generation_lock.release()
            note = "已通过结构与原文引用校验；答案正确性、引用相关性和教学质量仍需人工审查。"
        with db.connect(write=True) as con:
            saved = save_questions(
                con,
                item.material_id,
                generated,
                "demo-curated" if item.mode == "demo" else "openai-compatible",
            )
            con.execute(
                "INSERT INTO generation_runs(material_id,mode,requested_count,status,created_at) "
                "VALUES(?,?,?,?,?)",
                (item.material_id, item.mode, item.count, "success", now()),
            )
        return {"questions": saved, "mode": item.mode, "note": note}

    @app.post("/api/quizzes", status_code=201)
    def start_quiz(item: QuizInput):
        with db.connect(write=True) as con:
            selected = []
            for question_id in item.question_ids:
                row = con.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
                if row is None:
                    raise HTTPException(404, "选择的题目不存在")
                if (
                    item.mode == "wrongbook"
                    and not con.execute(
                        "SELECT 1 FROM wrong_answers WHERE question_id=?", (question_id,)
                    ).fetchone()
                ):
                    raise HTTPException(422, "错题重练只能选择错题本中的题目")
                q = question_dict(row)
                selected.append(
                    {k: q[k] for k in ["id", "stem", "options", "knowledge_point", "difficulty"]}
                )
            cursor = con.execute(
                "INSERT INTO quiz_sessions(question_ids,mode,created_at,total) VALUES(?,?,?,?)",
                (json.dumps(item.question_ids), item.mode, now(), len(selected)),
            )
            return {"id": cursor.lastrowid, "questions": selected}

    @app.post("/api/quizzes/{quiz_id}/submit")
    def submit_quiz(quiz_id: int, item: SubmitInput):
        with db.connect(write=True) as con:
            quiz = con.execute("SELECT * FROM quiz_sessions WHERE id=?", (quiz_id,)).fetchone()
            if quiz is None:
                raise HTTPException(404, "练习不存在")
            if quiz["submitted_at"]:
                return quiz_result(con, quiz_id)
            ids = json.loads(quiz["question_ids"])
            if set(item.answers) - {str(qid) for qid in ids}:
                raise HTTPException(422, "答案中包含不属于本次练习的题目")
            correct, timestamp = 0, now()
            for qid in ids:
                answer = con.execute("SELECT answer FROM questions WHERE id=?", (qid,)).fetchone()[
                    "answer"
                ]
                selected = item.answers.get(str(qid))
                is_correct = selected == answer
                correct += int(is_correct)
                con.execute(
                    "INSERT INTO quiz_answers VALUES(?,?,?,?)",
                    (quiz_id, qid, selected, int(is_correct)),
                )
                if not is_correct:
                    con.execute(
                        "INSERT INTO "
                        "wrong_answers(question_id,wrong_count,last_wrong_at,"
                        "last_selected,mastered) VALUES(?,1,?,?,0) "
                        "ON CONFLICT(question_id) DO UPDATE SET wrong_count=wrong_count+1, "
                        "last_wrong_at=excluded.last_wrong_at, "
                        "last_selected=excluded.last_selected, mastered=0",
                        (qid, timestamp, selected),
                    )
                else:
                    con.execute("UPDATE wrong_answers SET mastered=1 WHERE question_id=?", (qid,))
            con.execute(
                "UPDATE quiz_sessions SET submitted_at=?,score=?,correct=? WHERE id=?",
                (timestamp, round(correct / len(ids) * 100, 1), correct, quiz_id),
            )
            return quiz_result(con, quiz_id)

    @app.get("/api/wrongbook")
    def wrongbook():
        with db.connect() as con:
            result = []
            for row in con.execute(
                "SELECT * FROM wrong_answers ORDER BY mastered,last_wrong_at DESC,question_id DESC"
            ).fetchall():
                entry = dict(row)
                entry["mastered"] = bool(entry["mastered"])
                entry["question"] = question_dict(
                    con.execute(
                        "SELECT * FROM questions WHERE id=?", (entry["question_id"],)
                    ).fetchone()
                )
                result.append(entry)
            return result

    @app.patch("/api/wrongbook/{question_id}")
    def set_mastered(question_id: int, item: MasteredInput):
        with db.connect(write=True) as con:
            changed = con.execute(
                "UPDATE wrong_answers SET mastered=? WHERE question_id=?",
                (int(item.mastered), question_id),
            )
            if changed.rowcount == 0:
                raise HTTPException(404, "错题记录不存在")
        return {"question_id": question_id, "mastered": item.mastered}

    @app.get("/api/history")
    def history():
        with db.connect() as con:
            return [
                dict(r)
                for r in con.execute(
                    "SELECT id,score,correct,total,mode,created_at,submitted_at FROM "
                    "quiz_sessions WHERE submitted_at IS NOT NULL ORDER BY id DESC"
                ).fetchall()
            ]

    @app.get("/api/history/{quiz_id}")
    def history_item(quiz_id: int):
        with db.connect() as con:
            return quiz_result(con, quiz_id)

    @app.get("/api/stats")
    def stats():
        with db.connect() as con:
            result = {
                "materials": con.execute("SELECT COUNT(*) FROM materials").fetchone()[0],
                "questions": con.execute("SELECT COUNT(*) FROM questions").fetchone()[0],
                "quiz_count": con.execute(
                    "SELECT COUNT(*) FROM quiz_sessions WHERE submitted_at IS NOT NULL"
                ).fetchone()[0],
                "wrong_count": con.execute(
                    "SELECT COUNT(*) FROM wrong_answers WHERE mastered=0"
                ).fetchone()[0],
            }
            total, correct = con.execute(
                "SELECT COUNT(*),COALESCE(SUM(is_correct),0) FROM quiz_answers"
            ).fetchone()
            result.update(
                total_answered=total, accuracy=round(correct / total * 100, 1) if total else 0
            )
            result["recent_scores"] = [
                dict(r)
                for r in con.execute(
                    "SELECT id,score,created_at FROM quiz_sessions WHERE submitted_at IS NOT "
                    "NULL ORDER BY id DESC LIMIT 10"
                ).fetchall()
            ]
            result["knowledge_points"] = [
                dict(r)
                for r in con.execute(
                    "SELECT q.knowledge_point,COUNT(*) AS total,SUM(a.is_correct) AS "
                    "correct,ROUND(100.0*SUM(a.is_correct)/COUNT(*),1) AS accuracy FROM "
                    "quiz_answers a JOIN questions q ON a.question_id=q.id GROUP BY "
                    "q.knowledge_point ORDER BY total DESC,q.knowledge_point"
                ).fetchall()
            ]
            return result

    @app.get("/api/export")
    def export_bank():
        with db.connect() as con:
            material_rows = con.execute(
                "SELECT id,title,course,text FROM materials ORDER BY id"
            ).fetchall()
            questions = [
                question_dict(r)
                for r in con.execute("SELECT * FROM questions ORDER BY id").fetchall()
            ]
        if not material_rows:
            raise HTTPException(409, "还没有可导出的资料")
        if len(material_rows) > 100 or len(questions) > 500:
            raise HTTPException(409, "题库超过单文件导入上限，请停止服务后备份 data/ 目录")
        fields = set(QuestionInput.model_fields) | {"material_id"}
        payload = {
            "format": "quiz-study-v1",
            "materials": [dict(r) for r in material_rows],
            "questions": [{k: q[k] for k in fields} for q in questions],
        }
        exported = json.dumps(payload, ensure_ascii=False, indent=2)
        if len(exported.encode("utf-8")) > settings.upload_limit_bytes:
            raise HTTPException(409, "题库超过 5 MB 导入上限，请停止服务后备份 data/ 目录")
        return Response(
            exported,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="quiz-study-export.json"'},
        )

    @app.post("/api/import")
    async def import_bank(file: Annotated[UploadFile, File()]):
        try:
            content = await file.read(settings.upload_limit_bytes + 1)
            if len(content) > settings.upload_limit_bytes:
                raise HTTPException(413, "导入文件最多 5 MB")
            bundle = ImportBundle.model_validate_json(content)
            material_ids = [m.id for m in bundle.materials]
            if len(set(material_ids)) != len(material_ids):
                raise ValueError("duplicate ids")
            sources = {m.id: m.text for m in bundle.materials}
            for question in bundle.questions:
                if question.material_id not in sources:
                    raise ValueError("missing material")
                validate_questions([question], sources[question.material_id])
        except (ValidationError, ValueError, GenerationError):
            raise HTTPException(
                422, "导入失败：格式、资料关联或原文引用不符合 quiz-study-v1 规范，未写入任何数据"
            ) from None
        finally:
            await file.close()
        with db.connect(write=True) as con:
            mapping = {}
            for material in bundle.materials:
                data = material.model_dump(exclude={"id"})
                mapping[material.id] = save_material(con, MaterialInput(**data))["id"]
            for question in bundle.questions:
                data = question.model_dump(exclude={"material_id"})
                save_questions(
                    con, mapping[question.material_id], [QuestionInput(**data)], "imported"
                )
        return {"materials": len(bundle.materials), "questions": len(bundle.questions)}

    return app


app = create_app()
