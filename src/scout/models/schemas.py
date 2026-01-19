from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class ContentType(str, Enum):
    ARTICLE = "article"
    TWITTER = "twitter"
    YOUTUBE = "youtube"
    UNKNOWN = "unknown"


class RelevanceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewRequest(BaseModel):
    url: HttpUrl
    project: str = Field(..., min_length=1, description="Project name from BrainDrive-Library")
    content: Optional[str] = Field(None, description="Optional manual content if URL fetch fails")


class ReviewResponse(BaseModel):
    url: str
    project: str
    title: str
    content_type: ContentType
    relevance: RelevanceLevel
    insights: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    logged_at: datetime


class ProjectInfo(BaseModel):
    name: str
    description: Optional[str] = None
    path: str


class ProjectListResponse(BaseModel):
    projects: list[ProjectInfo]


class FetchedContent(BaseModel):
    url: str
    title: str
    content: str
    content_type: ContentType


class ProjectContext(BaseModel):
    name: str
    spec: Optional[str] = None
    build_plan: Optional[str] = None
    ideas: Optional[str] = None

    def get_combined_context(self) -> str:
        parts = []
        if self.spec:
            parts.append(f"## Project Specification\n\n{self.spec}")
        if self.build_plan:
            parts.append(f"## Build Plan\n\n{self.build_plan}")
        if self.ideas:
            parts.append(f"## Ideas\n\n{self.ideas}")
        return "\n\n---\n\n".join(parts) if parts else "No project context available."


class AnalysisResult(BaseModel):
    relevance: RelevanceLevel
    insights: list[str]
    suggestions: list[str]


class ErrorResponse(BaseModel):
    detail: str


class ProjectRelevance(BaseModel):
    """Relevance result for a single project in multi-project analysis."""
    project: str
    relevance: RelevanceLevel
    insights: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class MultiProjectReviewResponse(BaseModel):
    """Response when analyzing against all projects."""
    url: str
    title: str
    content_type: ContentType
    results: list[ProjectRelevance] = Field(default_factory=list)
    logged_at: datetime
