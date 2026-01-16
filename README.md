# BrainDrive Scout

A lightweight, mobile-friendly tool for reviewing external resources (articles, X posts, YouTube videos) against active BrainDrive projects. Returns relevance analysis without modifying project files.

## Features

- **URL Analysis**: Paste any URL and get instant relevance analysis
- **Content Types**: Supports web articles, X/Twitter posts, and YouTube videos (via transcript)
- **Project Context**: Loads project specs from your BrainDrive-Library
- **AI Analysis**: Uses Claude to compare content against project goals
- **Research Logging**: Automatically logs reviewed resources per project

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/BrainDrive-Scout.git
cd BrainDrive-Scout
pip install -e .
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required environment variables:
- `ANTHROPIC_API_KEY`: Your Anthropic API key
- `GITHUB_TOKEN`: GitHub token with repo access
- `LIBRARY_REPO`: Your BrainDrive-Library repo (e.g., `yourusername/BrainDrive-Library`)

### 3. Run Locally

```bash
python -m scout.main
```

Or with uvicorn directly:

```bash
uvicorn scout.main:app --reload
```

Visit http://localhost:8000 to use the web interface.

## API Endpoints

### `GET /api/projects`

Returns list of available projects from your BrainDrive-Library.

### `POST /api/review`

Analyze a URL against a specific project.

**Request:**
```json
{
  "url": "https://example.com/article",
  "project": "braindrive-lib"
}
```

**Response:**
```json
{
  "url": "https://example.com/article",
  "project": "braindrive-lib",
  "title": "Article Title",
  "content_type": "article",
  "relevance": "high",
  "insights": [
    "This article describes a similar workflow pattern",
    "The author's approach could improve our extraction"
  ],
  "suggestions": [
    "Consider adding their UX pattern to the librarian",
    "Their config approach could simplify our setup"
  ],
  "logged_at": "2026-01-16T14:30:00Z"
}
```

## Project Structure

```
BrainDrive-Scout/
├── src/scout/
│   ├── main.py           # FastAPI app
│   ├── config.py         # Settings management
│   ├── api/
│   │   └── routes.py     # API endpoints
│   ├── services/
│   │   ├── fetcher.py    # Content extraction
│   │   ├── context.py    # Project context loading
│   │   ├── analyzer.py   # Claude analysis
│   │   └── logger.py     # Research logging
│   └── models/
│       └── schemas.py    # Pydantic models
├── static/
│   └── index.html        # Web interface
├── logs/                  # Research logs by project
├── Dockerfile
└── pyproject.toml
```

## BrainDrive-Library Structure

Scout expects your library repo to have project directories containing:
- `spec.md` - Project specification
- `build-plan.md` - Implementation plan (optional)
- `ideas.md` - Ideas and notes (optional)

Example:
```
BrainDrive-Library/
├── braindrive-lib/
│   ├── spec.md
│   ├── build-plan.md
│   └── ideas.md
├── another-project/
│   └── spec.md
```

## Docker Deployment

```bash
docker build -t braindrive-scout .
docker run -p 8000:8000 --env-file .env braindrive-scout
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/
```

## License

MIT
