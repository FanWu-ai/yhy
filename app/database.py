"""Small SQLite repository. All mutations are atomic and all SQL is parameterized."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    course TEXT NOT NULL,
    filename TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_material_hash ON materials(content_hash);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY,
    material_id INTEGER NOT NULL REFERENCES materials(id),
    stem TEXT NOT NULL,
    options TEXT NOT NULL,
    answer INTEGER NOT NULL CHECK(answer BETWEEN 0 AND 3),
    explanation TEXT NOT NULL,
    source_quote TEXT NOT NULL,
    knowledge_point TEXT NOT NULL,
    difficulty TEXT NOT NULL CHECK(difficulty IN ('easy', 'medium', 'hard')),
    generator TEXT NOT NULL,
    fingerprint TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quiz_sessions (
    id INTEGER PRIMARY KEY,
    question_ids TEXT NOT NULL,
    mode TEXT NOT NULL,
    created_at TEXT NOT NULL,
    submitted_at TEXT,
    score REAL,
    correct INTEGER,
    total INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS quiz_answers (
    quiz_id INTEGER NOT NULL REFERENCES quiz_sessions(id),
    question_id INTEGER NOT NULL REFERENCES questions(id),
    selected INTEGER CHECK(selected BETWEEN 0 AND 3),
    is_correct INTEGER NOT NULL,
    PRIMARY KEY(quiz_id, question_id)
);
CREATE TABLE IF NOT EXISTS wrong_answers (
    question_id INTEGER PRIMARY KEY REFERENCES questions(id),
    wrong_count INTEGER NOT NULL DEFAULT 1,
    last_wrong_at TEXT NOT NULL,
    last_selected INTEGER,
    mastered INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS generation_runs (
    id INTEGER PRIMARY KEY,
    material_id INTEGER NOT NULL REFERENCES materials(id),
    mode TEXT NOT NULL,
    requested_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript(SCHEMA)

    @contextmanager
    def connect(self, write: bool = False):
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA busy_timeout = 15000")
        try:
            if write:
                con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
