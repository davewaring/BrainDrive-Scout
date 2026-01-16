import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

from scout.models.schemas import ContentType, FetchedContent


class ContentFetcher:
    def __init__(self):
        self.timeout = httpx.Timeout(30.0)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

    def detect_content_type(self, url: str) -> ContentType:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        if "twitter.com" in domain or "x.com" in domain:
            return ContentType.TWITTER
        elif "youtube.com" in domain or "youtu.be" in domain:
            return ContentType.YOUTUBE
        else:
            return ContentType.ARTICLE

    async def fetch(self, url: str) -> FetchedContent:
        content_type = self.detect_content_type(url)

        if content_type == ContentType.YOUTUBE:
            return await self._fetch_youtube(url)
        elif content_type == ContentType.TWITTER:
            return await self._fetch_twitter(url)
        else:
            return await self._fetch_article(url)

    async def _fetch_article(self, url: str) -> FetchedContent:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract title
        title = ""
        if soup.title:
            title = soup.title.string or ""
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title:
                title = og_title.get("content", "")

        # Remove unwanted elements
        for element in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
            element.decompose()

        # Try to find main content
        main_content = None
        for selector in ["article", "main", '[role="main"]', ".post-content", ".article-content"]:
            main_content = soup.select_one(selector)
            if main_content:
                break

        if main_content:
            text = main_content.get_text(separator="\n", strip=True)
        else:
            # Fallback to body
            body = soup.body
            text = body.get_text(separator="\n", strip=True) if body else ""

        # Clean up whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        content = "\n".join(lines)

        # Truncate if too long (keep first ~10k chars for analysis)
        if len(content) > 10000:
            content = content[:10000] + "\n\n[Content truncated...]"

        return FetchedContent(
            url=url,
            title=title.strip() if title else "Untitled Article",
            content=content,
            content_type=ContentType.ARTICLE,
        )

    async def _fetch_youtube(self, url: str) -> FetchedContent:
        video_id = self._extract_youtube_id(url)
        if not video_id:
            raise ValueError(f"Could not extract YouTube video ID from URL: {url}")

        # Get video title
        title = await self._get_youtube_title(url)

        # Get transcript
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            transcript_text = " ".join([entry["text"] for entry in transcript_list])
        except (TranscriptsDisabled, NoTranscriptFound) as e:
            transcript_text = f"[Transcript not available: {str(e)}]"
        except Exception as e:
            transcript_text = f"[Error fetching transcript: {str(e)}]"

        # Truncate if too long
        if len(transcript_text) > 15000:
            transcript_text = transcript_text[:15000] + "\n\n[Transcript truncated...]"

        return FetchedContent(
            url=url,
            title=title,
            content=transcript_text,
            content_type=ContentType.YOUTUBE,
        )

    def _extract_youtube_id(self, url: str) -> str | None:
        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
            r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
            r"youtube\.com/v/([a-zA-Z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def _get_youtube_title(self, url: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=self.headers)
                soup = BeautifulSoup(response.text, "html.parser")
                if soup.title:
                    title = soup.title.string or ""
                    # Remove " - YouTube" suffix
                    title = re.sub(r"\s*-\s*YouTube\s*$", "", title)
                    return title.strip()
        except Exception:
            pass
        return "YouTube Video"

    async def _fetch_twitter(self, url: str) -> FetchedContent:
        # Try using nitter instances as fallback for public access
        nitter_instances = [
            "nitter.net",
            "nitter.privacydev.net",
        ]

        parsed = urlparse(url)
        path = parsed.path

        content = ""
        title = "X/Twitter Post"

        # First try direct fetch (works for some public posts)
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")

                    # Try to get og:description which often contains tweet text
                    og_desc = soup.find("meta", property="og:description")
                    if og_desc:
                        content = og_desc.get("content", "")

                    og_title = soup.find("meta", property="og:title")
                    if og_title:
                        title = og_title.get("content", "") or title
        except Exception:
            pass

        # Try nitter instances if direct fetch didn't get content
        if not content:
            for nitter in nitter_instances:
                try:
                    nitter_url = f"https://{nitter}{path}"
                    async with httpx.AsyncClient(
                        timeout=self.timeout, follow_redirects=True
                    ) as client:
                        response = await client.get(nitter_url, headers=self.headers)
                        if response.status_code == 200:
                            soup = BeautifulSoup(response.text, "html.parser")

                            # Nitter shows tweet content in specific elements
                            tweet_content = soup.select_one(".tweet-content")
                            if tweet_content:
                                content = tweet_content.get_text(strip=True)
                                break
                except Exception:
                    continue

        if not content:
            content = "[Could not fetch tweet content. The post may be protected or require authentication.]"

        return FetchedContent(
            url=url,
            title=title,
            content=content,
            content_type=ContentType.TWITTER,
        )


# Singleton instance
fetcher = ContentFetcher()
