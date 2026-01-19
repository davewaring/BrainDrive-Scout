import json
import re

from anthropic import Anthropic

from scout.models.schemas import (
    AnalysisResult,
    ChatMessage,
    FetchedContent,
    ProjectContext,
    RelevanceLevel,
)

ANALYSIS_PROMPT = """You are a research analyst helping evaluate whether external content is relevant to a software project.

## Project Context
Project Name: {project_name}

{project_context}

## Content to Analyze
Title: {content_title}
Type: {content_type}
URL: {content_url}

Content:
{content_text}

## Your Task
Analyze how relevant this content is to the project above. Consider:
- Does it address problems the project is trying to solve?
- Does it describe techniques, patterns, or approaches applicable to the project?
- Does it contain insights that could improve the project's design or implementation?
- Does it cover related technologies or integrations mentioned in the project?

Respond with a JSON object in this exact format:
{{
  "relevance": "high" | "medium" | "low",
  "insights": [
    "Insight 1 - specific observation about how this content relates to the project",
    "Insight 2 - another relevant observation"
  ],
  "suggestions": [
    "Suggestion 1 - specific actionable idea for the project based on this content",
    "Suggestion 2 - another actionable suggestion"
  ]
}}

Guidelines for relevance levels:
- "high": Directly applicable to core project goals, describes similar systems, or offers immediately useful patterns
- "medium": Tangentially related, covers adjacent topics, or provides general best practices that could help
- "low": Minimal connection to project goals, mostly unrelated content

Provide 2-4 insights and 1-3 suggestions. Be specific and reference both the content and project details.
Only output the JSON object, no other text."""


class Analyzer:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"

    async def analyze(
        self, content: FetchedContent, project_context: ProjectContext
    ) -> AnalysisResult:
        prompt = ANALYSIS_PROMPT.format(
            project_name=project_context.name,
            project_context=project_context.get_combined_context(),
            content_title=content.title,
            content_type=content.content_type.value,
            content_url=content.url,
            content_text=content.content,
        )

        # Use synchronous client (anthropic SDK handles this well)
        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text

        # Parse JSON response
        try:
            # Try to extract JSON from the response
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                result_data = json.loads(json_match.group())
            else:
                result_data = json.loads(response_text)

            return AnalysisResult(
                relevance=RelevanceLevel(result_data.get("relevance", "low")),
                insights=result_data.get("insights", []),
                suggestions=result_data.get("suggestions", []),
            )
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback if parsing fails
            return AnalysisResult(
                relevance=RelevanceLevel.LOW,
                insights=[f"Analysis parsing error: {str(e)}"],
                suggestions=["Please try again or review the content manually"],
            )

    async def chat(
        self,
        messages: list[ChatMessage],
        project_context: ProjectContext,
        analysis_context: str,
        initial_analysis: str,
    ) -> str:
        """Continue a conversation about analyzed content."""
        system_prompt = f"""You are a research assistant helping discuss content that was analyzed for relevance to a software project.

## Project Context
Project Name: {project_context.name}

{project_context.get_combined_context()}

## Original Analyzed Content
{analysis_context}

## Initial Analysis Results
{initial_analysis}

## Your Role
Help the user explore this content further. You can:
- Explain insights in more detail
- Discuss how specific parts of the content apply to the project
- Suggest implementation approaches based on the content
- Answer questions about the content or the analysis
- Provide additional context or clarification

Be concise but thorough. Reference specific parts of the content when relevant."""

        # Convert ChatMessage objects to dicts for the API
        api_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

        message = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system_prompt,
            messages=api_messages,
        )

        return message.content[0].text


# Factory function
_analyzer_instance: Analyzer | None = None


def get_analyzer(api_key: str) -> Analyzer:
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = Analyzer(api_key)
    return _analyzer_instance


def reset_analyzer():
    """Reset the analyzer instance (useful for testing)."""
    global _analyzer_instance
    _analyzer_instance = None
