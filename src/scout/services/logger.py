import os
from datetime import datetime
from pathlib import Path

from scout.models.schemas import AnalysisResult, FetchedContent


class ResearchLogger:
    def __init__(self, logs_dir: str = "logs"):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)

    def log_review(
        self,
        project_name: str,
        content: FetchedContent,
        analysis: AnalysisResult,
    ) -> datetime:
        """Append a review entry to the project's log file."""
        log_file = self.logs_dir / f"{project_name}.md"
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")

        # Check if file exists and if we need to add date header
        file_exists = log_file.exists()
        needs_date_header = True

        if file_exists:
            existing_content = log_file.read_text()
            # Check if today's date header already exists
            if f"## {date_str}" in existing_content:
                needs_date_header = False
        else:
            existing_content = ""

        # Build the entry
        entry_parts = []

        if not file_exists:
            # Create file with main header
            entry_parts.append(f"# Research Log: {project_name}\n")

        if needs_date_header:
            entry_parts.append(f"\n## {date_str}\n")

        # Add the review entry
        entry_parts.append(f"\n### [{content.title}]({content.url})")
        entry_parts.append(f"*Reviewed at {time_str} | Type: {content.content_type.value}*\n")
        entry_parts.append(f"- **Relevance**: {analysis.relevance.value}")

        if analysis.insights:
            entry_parts.append("- **Key insights**:")
            for insight in analysis.insights:
                entry_parts.append(f"  - {insight}")

        if analysis.suggestions:
            entry_parts.append("- **Suggestions**:")
            for suggestion in analysis.suggestions:
                entry_parts.append(f"  - {suggestion}")

        entry_parts.append("")  # Blank line at end

        entry = "\n".join(entry_parts)

        # Append to file
        with open(log_file, "a") as f:
            f.write(entry)

        return now


# Singleton instance
_logger_instance: ResearchLogger | None = None


def get_research_logger(logs_dir: str = "logs") -> ResearchLogger:
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = ResearchLogger(logs_dir)
    return _logger_instance


def reset_research_logger():
    """Reset the logger instance (useful for testing)."""
    global _logger_instance
    _logger_instance = None
