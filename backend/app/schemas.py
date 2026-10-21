from typing import Literal

from pydantic import BaseModel, Field


class ImportRequest(BaseModel):
    url: str = Field(min_length=1, max_length=300)


class TaskRequest(BaseModel):
    repository_id: str
    prompt: str = Field(min_length=5, max_length=4000)
    provider: Literal["demo", "openai"] = "demo"
    variant: Literal["A", "B", "C", "D"] = "D"
    retrieval: Literal["keyword", "vector", "hybrid"] = "hybrid"


class ApprovalRequest(BaseModel):
    approved: bool
    patch_digest: str = Field(min_length=64, max_length=64)


class Edit(BaseModel):
    path: str
    old: str = Field(min_length=1, max_length=20000)
    new: str = Field(max_length=20000)


class Plan(BaseModel):
    steps: list[str] = Field(min_length=1, max_length=8)
    rationale: str = Field(max_length=3000)


class Proposal(BaseModel):
    summary: str = Field(max_length=3000)
    edits: list[Edit] = Field(max_length=8)


class Review(BaseModel):
    approved: bool
    findings: list[str] = Field(max_length=12)
