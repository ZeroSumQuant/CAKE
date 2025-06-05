#!/usr/bin/env python3
"""info_fetcher.py - Intelligent Documentation Retrieval for CAKE

Provides controlled, efficient access to external documentation and resources
without using LLM-powered search. Focuses on deterministic, cacheable lookups.

Author: CAKE Team
License: MIT
Python: 3.11+
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import aiofiles
import aiohttp
from bs4 import BeautifulSoup

# Configure module logger
logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Represents a single search result.

    Attributes:
        source: Where the result came from
        url: URL of the resource
        title: Title of the resource
        snippet: Relevant excerpt
        relevance_score: 0.0-1.0 relevance rating
        metadata: Additional information
    """

    source: str
    url: str
    title: str
    snippet: str
    relevance_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class DocumentationSource:
    """Base class for documentation sources."""

    def __init__(self, name: str, base_url: str, cache_dir: Path):
        self.name = name
        self.base_url = base_url
        self.cache_dir = cache_dir / name
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Search this source for documentation."""
        raise NotImplementedError

    def _get_cache_path(self, query: str) -> Path:
        """Get cache file path for query."""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return self.cache_dir / f"{query_hash}.json"

    async def _get_cached(
        self, query: str, max_age_hours: int = 24
    ) -> Optional[List[SearchResult]]:
        """Get cached results if fresh enough."""
        cache_path = self._get_cache_path(query)

        if not cache_path.exists():
            return None

        try:
            # Check age
            mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
            if datetime.now() - mtime > timedelta(hours=max_age_hours):
                return None

            # Load cached data
            async with aiofiles.open(cache_path, "r") as f:
                data = json.loads(await f.read())

            # Convert back to SearchResult objects
            results = []
            for item in data:
                item["timestamp"] = datetime.fromisoformat(item["timestamp"])
                results.append(SearchResult(**item))

            logger.info(f"Cache hit for '{query}' in {self.name}")
            return results

        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
            return None

    async def _cache_results(self, query: str, results: List[SearchResult]):
        """Cache search results."""
        cache_path = self._get_cache_path(query)

        try:
            data = [r.to_dict() for r in results]
            async with aiofiles.open(cache_path, "w") as f:
                await f.write(json.dumps(data, indent=2))

        except Exception as e:
            logger.warning(f"Cache write failed: {e}")


class OfficialDocsSource(DocumentationSource):
    """
    Searches official documentation sites.
    """

    # Known documentation patterns
    DOC_PATTERNS = {
        "python": {
            "base_url": "https://docs.python.org/3/",
            "search_url": "https://docs.python.org/3/search.html?q={query}",
            "parse_method": "python_docs",
        },
        "pip": {
            "base_url": "https://pip.pypa.io/en/stable/",
            "search_url": "https://pip.pypa.io/en/stable/search.html?q={query}",
            "parse_method": "sphinx_docs",
        },
        "pytest": {
            "base_url": "https://docs.pytest.org/en/stable/",
            "search_url": "https://docs.pytest.org/en/stable/search.html?q={query}",
            "parse_method": "sphinx_docs",
        },
        "django": {
            "base_url": "https://docs.djangoproject.com/en/stable/",
            "search_url": "https://docs.djangoproject.com/en/stable/search/?q={query}",
            "parse_method": "django_docs",
        },
        "fastapi": {
            "base_url": "https://fastapi.tiangolo.com/",
            "search_url": "https://fastapi.tiangolo.com/search/?q={query}",
            "parse_method": "mkdocs",
        },
    }

    def __init__(self, cache_dir: Path):
        super().__init__("official_docs", "https://docs.python.org", cache_dir)
        self.session = None

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Search official documentation."""  # Check cache first
        cached = await self._get_cached(query)
        if cached is not None:
            return cached[:max_results]

        # Detect which docs to search based on query
        doc_sources = self._detect_relevant_docs(query)

        # Search each relevant source
        all_results = []
        async with aiohttp.ClientSession() as self.session:
            tasks = []
            for source in doc_sources:
                task = self._search_doc_source(source, query)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, list):
                    all_results.extend(result)
                else:
                    logger.warning(f"Search task failed: {result}")

        # Sort by relevance
        all_results.sort(key=lambda x: x.relevance_score, reverse=True)

        # Cache results
        await self._cache_results(query, all_results[: max_results * 2])

        return all_results[:max_results]

    def _detect_relevant_docs(self, query: str) -> List[str]:
        """Detect which documentation sources are relevant."""
        query_lower = query.lower()
        relevant = []

        # Check for explicit mentions
        for source in self.DOC_PATTERNS:
            if source in query_lower:
                relevant.append(source)

        # Default to Python docs if no specific match
        if not relevant:
            relevant.append("python")

        # Add common tools for error-related queries
        if any(
            term in query_lower for term in ["error", "exception", "failed", "module"]
        ):
            if "pip" not in relevant:
                relevant.append("pip")
            if "pytest" not in relevant and "test" in query_lower:
                relevant.append("pytest")

        return relevant

    async def _search_doc_source(self, source: str, query: str) -> List[SearchResult]:
        """Search a specific documentation source."""
        if source not in self.DOC_PATTERNS:
            return []

        config = self.DOC_PATTERNS[source]
        search_url = config["search_url"].format(query=quote(query))

        try:
            # For demo purposes, return mock results
            # In production, would actually fetch and parse
            return self._create_mock_results(source, query)

        except Exception as e:
            logger.error(f"Failed to search {source}: {e}")
            return []

    def _create_mock_results(self, source: str, query: str) -> List[SearchResult]:
        """Create mock results for demonstration."""  # In production, would parse actual HTML
        mock_data = {
            "python": [
                SearchResult(
                    source="Python Docs",
                    url=f"https://docs.python.org/3/library/{query.split()[0]}.html",
                    title=f"{query.split()[0]} — Python 3 documentation",
                    snippet=f"Documentation for {query} in Python's standard library...",
                    relevance_score=0.9,
                )
            ],
            "pip": [
                SearchResult(
                    source="pip Documentation",
                    url="https://pip.pypa.io/en/stable/cli/pip_install/",
                    title="pip install - pip documentation",
                    snippet="Install packages from PyPI, version control, local projects...",
                    relevance_score=0.85,
                )
            ],
        }

        return mock_data.get(source, [])


class StackOverflowSource(DocumentationSource):
    """
    Searches Stack Overflow for solutions.
    """

    API_BASE = "https://api.stackexchange.com/2.3"

    def __init__(self, cache_dir: Path):
        super().__init__("stackoverflow", self.API_BASE, cache_dir)

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Search Stack Overflow."""  # Check cache
        cached = await self._get_cached(query)
        if cached is not None:
            return cached[:max_results]

        # Build API request
        params = {
            "order": "desc",
            "sort": "relevance",
            "q": query,
            "site": "stackoverflow",
            "filter": "withbody",
            "pagesize": max_results,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.API_BASE}/search", params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = self._parse_so_results(data)
                        await self._cache_results(query, results)
                        return results
                    else:
                        logger.error(f"SO API error: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"Stack Overflow search failed: {e}")
            return self._fallback_results(query)

    def _parse_so_results(self, data: Dict[str, Any]) -> List[SearchResult]:
        """Parse Stack Overflow API response."""
        results = []

        for item in data.get("items", []):
            # Calculate relevance based on score and accepted answer
            base_score = min(item.get("score", 0) / 100, 0.5)
            has_accepted = 0.3 if item.get("is_answered") else 0
            relevance = base_score + has_accepted + 0.2

            result = SearchResult(
                source="Stack Overflow",
                url=item.get("link", ""),
                title=item.get("title", ""),
                snippet=self._extract_snippet(item.get("body", "")),
                relevance_score=min(relevance, 1.0),
                metadata={
                    "score": item.get("score", 0),
                    "answers": item.get("answer_count", 0),
                    "accepted": item.get("is_answered", False),
                    "tags": item.get("tags", []),
                },
            )
            results.append(result)

        return results

    def _extract_snippet(self, html_body: str) -> str:
        """Extract clean snippet from HTML."""
        try:
            soup = BeautifulSoup(html_body, "html.parser")
            text = soup.get_text()
            # Get first 200 chars
            snippet = " ".join(text.split())[:200]
            return snippet + "..." if len(text) > 200 else snippet
        except Exception:
            return "Content preview not available"

    def _fallback_results(self, query: str) -> List[SearchResult]:
        """Fallback results when API fails."""
        return [
            SearchResult(
                source="Stack Overflow",
                url=f"https://stackoverflow.com/search?q={quote(query)}",
                title="Search Stack Overflow",
                snippet=f"Search for '{query}' on Stack Overflow",
                relevance_score=0.5,
            )
        ]


class GitHubCodeSource(DocumentationSource):
    """
    Searches GitHub code for examples and implementations.
    """

    API_BASE = "https://api.github.com"

    def __init__(self, cache_dir: Path, token: Optional[str] = None):
        super().__init__("github", self.API_BASE, cache_dir)
        self.token = token

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Search GitHub code."""  # Check cache
        cached = await self._get_cached(query)
        if cached is not None:
            return cached[:max_results]

        # Add language hint for better results
        enhanced_query = (
            f"{query} language:python" if "python" not in query.lower() else query
        )

        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        params = {
            "q": enhanced_query,
            "sort": "stars",
            "order": "desc",
            "per_page": max_results,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.API_BASE}/search/code", headers=headers, params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = self._parse_github_results(data)
                        await self._cache_results(query, results)
                        return results
                    else:
                        logger.error(f"GitHub API error: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"GitHub search failed: {e}")
            return []

    def _parse_github_results(self, data: Dict[str, Any]) -> List[SearchResult]:
        """Parse GitHub API response."""
        results = []

        for item in data.get("items", []):
            repo = item.get("repository", {})

            # Calculate relevance
            stars = repo.get("stargazers_count", 0)
            relevance = min(0.5 + (stars / 10000), 1.0)

            result = SearchResult(
                source="GitHub Code",
                url=item.get("html_url", ""),
                title=f"{repo.get('name', 'Unknown')}/{item.get('name', 'file')}",
                snippet=self._format_code_context(item),
                relevance_score=relevance,
                metadata={
                    "repo": repo.get("full_name", ""),
                    "path": item.get("path", ""),
                    "stars": stars,
                    "language": repo.get("language", "Unknown"),
                },
            )
            results.append(result)

        return results

    def _format_code_context(self, item: Dict[str, Any]) -> str:
        """Format code context for display."""
        path = item.get("path", "unknown")
        repo = item.get("repository", {}).get("full_name", "repo")
        return f"Code example from {repo} at {path}"


class InfoFetcher:
    """
    Main information fetcher that coordinates multiple sources.
    """

    def __init__(self, cache_dir: Path, github_token: Optional[str] = None):
        """
        Initialize fetcher with all sources.

        Args:
            cache_dir: Directory for caching results
            github_token: Optional GitHub API token for better rate limits
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize sources
        self.sources = {
            "official_docs": OfficialDocsSource(cache_dir),
            "stackoverflow": StackOverflowSource(cache_dir),
            "github": GitHubCodeSource(cache_dir, github_token),
        }

        # Query enhancement patterns
        self.enhancement_patterns = {
            "error": ["fix", "solution", "resolve"],
            "install": ["pip", "setup", "requirements"],
            "import": ["module", "package", "dependency"],
            "test": ["pytest", "unittest", "testing"],
        }

        logger.info(f"InfoFetcher initialized with {len(self.sources)} sources")

    async def search(
        self, query: str, sources: Optional[List[str]] = None, max_results: int = 10
    ) -> str:
        """
        Search for documentation across sources.

        Args:
            query: Search query
            sources: List of sources to search (None = all)
            max_results: Maximum results to return

        Returns:
            Formatted string of results for Claude
        """  # Enhance query
        enhanced_query = self._enhance_query(query)
        logger.info(f"Searching for: '{enhanced_query}' (original: '{query}')")

        # Determine which sources to use
        if sources is None:
            sources = list(self.sources.keys())

        # Search all requested sources in parallel
        tasks = []
        for source_name in sources:
            if source_name in self.sources:
                source = self.sources[source_name]
                task = source.search(enhanced_query, max_results=max_results)
                tasks.append((source_name, task))

        # Gather results
        all_results = []
        for source_name, task in tasks:
            try:
                results = await task
                all_results.extend(results)
                logger.info(f"Got {len(results)} results from {source_name}")
            except Exception as e:
                logger.error(f"Source {source_name} failed: {e}")

        # Sort by relevance
        all_results.sort(key=lambda x: x.relevance_score, reverse=True)

        # Format for Claude
        return self._format_results(all_results[:max_results])

    def _enhance_query(self, query: str) -> str:
        """Enhance query for better search results."""
        query_lower = query.lower()

        # Add context terms based on patterns
        additions = []
        for key, terms in self.enhancement_patterns.items():
            if key in query_lower and not any(term in query_lower for term in terms):
                additions.append(terms[0])

        # Add Python context if not present
        if "python" not in query_lower and not any(
            lang in query_lower for lang in ["java", "javascript", "ruby", "go"]
        ):
            additions.append("python")

        # Combine
        enhanced = query
        if additions:
            enhanced = f"{query} {' '.join(additions)}"

        return enhanced

    def _format_results(self, results: List[SearchResult]) -> str:
        """Format search results for Claude consumption."""
        if not results:
            return "No relevant documentation found for this query."

        formatted = [
            "# Documentation Search Results\n",
            f"Found {len(results)} relevant resources:\n",
        ]

        # Group by source
        by_source = {}
        for result in results:
            if result.source not in by_source:
                by_source[result.source] = []
            by_source[result.source].append(result)

        # Format each source
        for source, source_results in by_source.items():
            formatted.append(f"\n## {source}\n")

            for i, result in enumerate(source_results, 1):
                formatted.append(f"### {i}. {result.title}")
                formatted.append(f"**URL**: {result.url}")
                formatted.append(f"**Relevance**: {result.relevance_score:.0%}")

                # Add metadata if useful
                if result.metadata:
                    if "score" in result.metadata:
                        formatted.append(f"**Score**: {result.metadata['score']}")
                    if "tags" in result.metadata:
                        formatted.append(
                            f"**Tags**: {', '.join(result.metadata['tags'])}"
                        )

                formatted.append(f"\n{result.snippet}\n")

        # Add search suggestions
        formatted.append("\n## Search Suggestions")
        formatted.append("- Refine your search with more specific terms")
        formatted.append("- Check the official documentation links above")
        formatted.append("- Look for similar issues in the Stack Overflow results")

        return "\n".join(formatted)

    async def fetch_url_content(self, url: str) -> Optional[str]:
        """
        Fetch and extract content from a specific URL.

        Args:
            url: URL to fetch

        Returns:
            Extracted text content or None if failed
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        html = await response.text()
                        return self._extract_content(html, url)
                    else:
                        logger.error(f"Failed to fetch {url}: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _extract_content(self, html: str, url: str) -> str:
        """Extract relevant content from HTML."""
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Try to find main content
            main_content = (
                soup.find("main")
                or soup.find("article")
                or soup.find(class_="content")
                or soup.find(class_="documentation")
                or soup.body
            )

            if main_content:
                text = main_content.get_text(separator="\n", strip=True)
                # Limit length
                if len(text) > 5000:
                    text = text[:5000] + "\n\n[Content truncated]"
                return f"Content from {url}:\n\n{text}"
            else:
                return "Could not extract main content from page"

        except Exception as e:
            logger.error(f"Content extraction failed: {e}")
            return "Failed to parse page content"

    def clear_cache(self, max_age_days: int = 7):
        """Clear old cache entries."""
        cutoff = datetime.now() - timedelta(days=max_age_days)
        cleared = 0

        for source_dir in self.cache_dir.iterdir():
            if source_dir.is_dir():
                for cache_file in source_dir.glob("*.json"):
                    try:
                        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                        if mtime < cutoff:
                            cache_file.unlink()
                            cleared += 1
                    except Exception as e:
                        logger.warning(f"Failed to clear cache file: {e}")

        logger.info(f"Cleared {cleared} old cache entries")
        return cleared

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {"total_files": 0, "total_size_mb": 0, "by_source": {}}

        for source_dir in self.cache_dir.iterdir():
            if source_dir.is_dir():
                source_stats = {"files": 0, "size_mb": 0}

                for cache_file in source_dir.glob("*.json"):
                    source_stats["files"] += 1
                    source_stats["size_mb"] += cache_file.stat().st_size / 1024 / 1024

                stats["by_source"][source_dir.name] = source_stats
                stats["total_files"] += source_stats["files"]
                stats["total_size_mb"] += source_stats["size_mb"]

        return stats


# Example usage and testing
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Create fetcher
    fetcher = InfoFetcher(Path("./info_cache"))

    async def test_searches():
        # Test different queries
        test_queries = [
            "ModuleNotFoundError requests",
            "pytest fixture not found",
            "python async await tutorial",
            "permission denied error",
        ]

        for query in test_queries:
            print(f"\n{'='*60}")
            print(f"Searching for: {query}")
            print("=" * 60)

            results = await fetcher.search(query, max_results=3)
            print(results)

    # Run tests
    asyncio.run(test_searches())

    # Show cache stats
    print("\nCache Statistics:")
    stats = fetcher.get_cache_stats()
    print(json.dumps(stats, indent=2))
