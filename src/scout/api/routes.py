from fastapi import APIRouter, Depends, HTTPException

from scout.config import Settings, get_settings
from scout.models.schemas import (
    ErrorResponse,
    ProjectListResponse,
    ReviewRequest,
    ReviewResponse,
)
from scout.services.analyzer import get_analyzer
from scout.services.context import get_context_loader
from scout.services.fetcher import fetcher
from scout.services.logger import get_research_logger

router = APIRouter()


@router.get(
    "/projects",
    response_model=ProjectListResponse,
    responses={500: {"model": ErrorResponse}},
)
async def list_projects(settings: Settings = Depends(get_settings)):
    """List all available projects from the BrainDrive-Library."""
    try:
        loader = get_context_loader(settings.github_token, settings.library_repo)
        projects = await loader.list_projects()
        return ProjectListResponse(projects=projects)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load projects: {str(e)}")


@router.post(
    "/review",
    response_model=ReviewResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def review_url(request: ReviewRequest, settings: Settings = Depends(get_settings)):
    """Review a URL against a specific project and return relevance analysis."""
    url_str = str(request.url)

    # 1. Fetch content from URL
    try:
        content = await fetcher.fetch(url_str)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch content: {str(e)}")

    # 2. Load project context
    try:
        loader = get_context_loader(settings.github_token, settings.library_repo)
        project_context = await loader.load_project_context(request.project)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load project context: {str(e)}")

    # Check if project has any context
    if not project_context.spec and not project_context.build_plan and not project_context.ideas:
        raise HTTPException(
            status_code=400,
            detail=f"Project '{request.project}' not found or has no context files",
        )

    # 3. Analyze with Claude
    try:
        analyzer = get_analyzer(settings.anthropic_api_key)
        analysis = await analyzer.analyze(content, project_context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    # 4. Log the review
    try:
        logger = get_research_logger(settings.logs_dir)
        logged_at = logger.log_review(request.project, content, analysis)
    except Exception as e:
        # Log failure shouldn't fail the request, but we note it
        logged_at = None
        print(f"Warning: Failed to log review: {e}")

    from datetime import datetime

    return ReviewResponse(
        url=url_str,
        project=request.project,
        title=content.title,
        content_type=content.content_type,
        relevance=analysis.relevance,
        insights=analysis.insights,
        suggestions=analysis.suggestions,
        logged_at=logged_at or datetime.now(),
    )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
