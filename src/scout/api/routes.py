from datetime import datetime
from typing import Union

from fastapi import APIRouter, Depends, HTTPException

from scout.config import Settings, get_settings
from scout.models.schemas import (
    ErrorResponse,
    MultiProjectReviewResponse,
    ProjectListResponse,
    ProjectRelevance,
    RelevanceLevel,
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
    response_model=Union[ReviewResponse, MultiProjectReviewResponse],
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def review_url(request: ReviewRequest, settings: Settings = Depends(get_settings)):
    """Review a URL against a specific project (or all projects) and return relevance analysis."""
    url_str = str(request.url)
    from scout.models.schemas import FetchedContent, ContentType

    # 1. Fetch content from URL (or use provided content as fallback)
    content = None
    fetch_error = None

    try:
        content = await fetcher.fetch(url_str)
    except Exception as e:
        fetch_error = str(e)

    # If fetch failed but manual content provided, use that instead
    if (content is None or not content.content.strip()) and request.content:
        # Determine content type from URL
        content_type = ContentType.UNKNOWN
        if "twitter.com" in url_str or "x.com" in url_str:
            content_type = ContentType.TWITTER
        elif "youtube.com" in url_str or "youtu.be" in url_str:
            content_type = ContentType.YOUTUBE
        else:
            content_type = ContentType.ARTICLE

        content = FetchedContent(
            url=url_str,
            title="Manual Content",
            content=request.content,
            content_type=content_type,
        )
    elif content is None:
        raise HTTPException(status_code=400, detail=f"Failed to fetch content: {fetch_error}")

    loader = get_context_loader(settings.github_token, settings.library_repo)
    analyzer = get_analyzer(settings.anthropic_api_key)
    research_logger = get_research_logger(settings.logs_dir)

    # Handle "all" projects case
    if request.project == "all":
        return await _review_all_projects(
            url_str, content, loader, analyzer, research_logger
        )

    # Single project review
    # 2. Load project context
    try:
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
        analysis = await analyzer.analyze(content, project_context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    # 4. Log the review
    try:
        logged_at = research_logger.log_review(request.project, content, analysis)
    except Exception as e:
        logged_at = None
        print(f"Warning: Failed to log review: {e}")

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


async def _review_all_projects(url_str, content, loader, analyzer, research_logger):
    """Analyze content against all projects and return sorted results."""
    try:
        projects = await loader.list_projects()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")

    results = []
    relevance_order = {RelevanceLevel.HIGH: 0, RelevanceLevel.MEDIUM: 1, RelevanceLevel.LOW: 2}

    for project_info in projects:
        try:
            project_context = await loader.load_project_context(project_info.name)

            # Skip projects with no context
            if not project_context.spec and not project_context.build_plan and not project_context.ideas:
                continue

            analysis = await analyzer.analyze(content, project_context)

            # Only include high and medium relevance results
            if analysis.relevance in (RelevanceLevel.HIGH, RelevanceLevel.MEDIUM):
                results.append(
                    ProjectRelevance(
                        project=project_info.name,
                        relevance=analysis.relevance,
                        insights=analysis.insights,
                        suggestions=analysis.suggestions,
                    )
                )

                # Log high/medium relevance reviews
                try:
                    research_logger.log_review(project_info.name, content, analysis)
                except Exception:
                    pass  # Don't fail on log errors

        except Exception as e:
            print(f"Warning: Failed to analyze project {project_info.name}: {e}")
            continue

    # Sort by relevance (high first)
    results.sort(key=lambda r: relevance_order.get(r.relevance, 99))

    return MultiProjectReviewResponse(
        url=url_str,
        title=content.title,
        content_type=content.content_type,
        results=results,
        logged_at=datetime.now(),
    )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
