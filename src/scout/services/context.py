import base64
from functools import lru_cache

import httpx

from scout.models.schemas import ProjectContext, ProjectInfo


class ContextLoader:
    def __init__(self, github_token: str, library_repo: str):
        self.github_token = github_token
        self.library_repo = library_repo
        self.base_url = "https://api.github.com"
        self.timeout = httpx.Timeout(30.0)

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def list_projects(self) -> list[ProjectInfo]:
        """List all project directories in projects/active/."""
        url = f"{self.base_url}/repos/{self.library_repo}/contents/projects/active"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=self._get_headers())
            response.raise_for_status()

        contents = response.json()
        projects = []

        for item in contents:
            if item["type"] == "dir" and not item["name"].startswith("."):
                # Try to get description from spec.md if it exists
                description = await self._get_project_description(item["name"])
                projects.append(
                    ProjectInfo(
                        name=item["name"],
                        description=description,
                        path=item["path"],
                    )
                )

        return projects

    async def _get_project_description(self, project_name: str) -> str | None:
        """Try to extract a brief description from the project's spec.md."""
        try:
            spec_content = await self._fetch_file(project_name, "spec.md")
            if spec_content:
                # Get first non-empty, non-header line as description
                lines = spec_content.split("\n")
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Truncate if too long
                        if len(line) > 100:
                            return line[:97] + "..."
                        return line
        except Exception:
            pass
        return None

    async def load_project_context(self, project_name: str) -> ProjectContext:
        """Load context files for a specific project."""
        spec = await self._fetch_file(project_name, "spec.md")
        build_plan = await self._fetch_file(project_name, "build-plan.md")
        ideas = await self._fetch_file(project_name, "ideas.md")

        return ProjectContext(
            name=project_name,
            spec=spec,
            build_plan=build_plan,
            ideas=ideas,
        )

    async def _fetch_file(self, project_name: str, filename: str) -> str | None:
        """Fetch a specific file from a project directory."""
        url = f"{self.base_url}/repos/{self.library_repo}/contents/projects/active/{project_name}/{filename}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self._get_headers())

                if response.status_code == 404:
                    return None

                response.raise_for_status()

            data = response.json()

            # GitHub returns file content as base64
            if "content" in data:
                content = base64.b64decode(data["content"]).decode("utf-8")
                return content

        except httpx.HTTPStatusError:
            return None
        except Exception:
            return None

        return None


# Factory function to create loader with settings
_loader_instance: ContextLoader | None = None


def get_context_loader(github_token: str, library_repo: str) -> ContextLoader:
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = ContextLoader(github_token, library_repo)
    return _loader_instance


def reset_context_loader():
    """Reset the loader instance (useful for testing)."""
    global _loader_instance
    _loader_instance = None
