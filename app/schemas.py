"""Reject malformed input before persistence or grading."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

Difficulty = Literal["easy", "medium", "hard"]
Answer = Annotated[StrictInt, Field(ge=0, le=3)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*")
    @classmethod
    def safe_unicode(cls, value):
        def validate(item):
            if isinstance(item, str):
                try:
                    item.encode("utf-8")
                except UnicodeEncodeError as exc:
                    raise ValueError("文本包含无效 Unicode 字符") from exc
                if "\x00" in item:
                    raise ValueError("文本不能包含 NUL 字符")
            elif isinstance(item, list):
                for child in item:
                    validate(child)
            elif isinstance(item, dict):
                for key, child in item.items():
                    validate(key)
                    validate(child)

        validate(value)
        return value


class MaterialInput(StrictModel):
    title: str = Field(min_length=1, max_length=120)
    course: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=20, max_length=30_000)

    @field_validator("text")
    @classmethod
    def no_nulls(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("资料不能包含 NUL 字符")
        return value


class QuestionInput(StrictModel):
    stem: str = Field(min_length=5, max_length=1000)
    options: list[str] = Field(min_length=4, max_length=4)
    answer: Answer
    explanation: str = Field(min_length=5, max_length=2000)
    source_quote: str = Field(min_length=5, max_length=1000)
    knowledge_point: str = Field(min_length=1, max_length=80)
    difficulty: Difficulty

    @field_validator("options")
    @classmethod
    def valid_options(cls, values: list[str]) -> list[str]:
        values = [v.strip() for v in values]
        if any(not v or len(v) > 500 for v in values) or len(set(values)) != 4:
            raise ValueError("必须提供四个不为空、不重复且不超过 500 字的选项")
        return values


class QuestionBatch(StrictModel):
    questions: list[QuestionInput] = Field(min_length=1, max_length=10)


class GenerateInput(StrictModel):
    material_id: int = Field(gt=0)
    count: int = Field(default=5, ge=1, le=10)
    difficulty: Difficulty = "easy"
    mode: Literal["demo", "openai"] = "demo"
    confirm_send: bool = False


class QuizInput(StrictModel):
    question_ids: list[StrictInt] = Field(min_length=1, max_length=50)
    mode: Literal["normal", "wrongbook"] = "normal"

    @field_validator("question_ids")
    @classmethod
    def unique_ids(cls, values: list[int]) -> list[int]:
        if len(values) != len(set(values)) or any(v < 1 for v in values):
            raise ValueError("题目 ID 必须为互不重复的正整数")
        return values


class SubmitInput(StrictModel):
    answers: dict[str, Answer] = Field(max_length=50)


class MasteredInput(StrictModel):
    mastered: bool


class ImportMaterial(MaterialInput):
    id: int = Field(gt=0)


class ImportQuestion(QuestionInput):
    material_id: int = Field(gt=0)


class ImportBundle(StrictModel):
    format: Literal["quiz-study-v1"]
    materials: list[ImportMaterial] = Field(min_length=1, max_length=100)
    questions: list[ImportQuestion] = Field(max_length=500)
