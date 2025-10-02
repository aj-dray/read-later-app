"""
Comprehensive text/markdown extraction comparison test.

Tests multiple extraction methods to compare content quality, cleanliness,
and markdown formatting. Run this to manually evaluate which method works best.

Note: this is a manual comparison tool that depends on optional libraries and
network access. To keep the automated backend test suite green in minimal
environments, we skip this module during pytest collection.
"""

import pytest
pytest.skip(
    "Skipping manual extraction comparison (optional deps/network)",
    allow_module_level=True,
)

import asyncio
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

# Add the server directory to the path
server_dir = Path(__file__).parent.parent
sys.path.insert(0, str(server_dir))

# Import current extraction method
from app.services.extracting import extract_data

# Alternative extraction libraries
import newspaper
from newspaper import Article
from readability import parse
import html2text
import requests
from bs4 import BeautifulSoup
from trafilatura import extract, fetch_url


class ExtractionMethod:
    """Base class for extraction methods."""

    def __init__(self, name: str):
        self.name = name

    def extract(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract content from URL. Returns (title, text, markdown)."""
        raise NotImplementedError


class CurrentMethod(ExtractionMethod):
    """Current trafilatura-based method."""

    def __init__(self):
        super().__init__("Current (Trafilatura Basic)")

    async def extract(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        item = await extract_data(url)
        if item:
            return item.title, item.text_content, item.markdown_content
        return None, None, None


class TrafilaturaEnhanced(ExtractionMethod):
    """Enhanced trafilatura with precision settings."""

    def __init__(self, favor_precision: bool = True):
        name = "Trafilatura (Precision)" if favor_precision else "Trafilatura (Recall)"
        super().__init__(name)
        self.favor_precision = favor_precision

    def extract(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        try:
            downloaded = fetch_url(url)
            if not downloaded:
                return None, None, None

            # Extract with enhanced settings
            text_content = extract(
                downloaded,
                output_format="txt",
                include_comments=False,
                include_tables=True,
                include_links=True,
                favor_precision=self.favor_precision,
                deduplicate=True,
            )

            markdown_content = extract(
                downloaded,
                output_format="markdown",
                include_comments=False,
                include_tables=True,
                include_links=True,
                favor_precision=self.favor_precision,
                deduplicate=True,
            )

            # Extract title using BeautifulSoup
            soup = BeautifulSoup(downloaded, 'html.parser')
            title = soup.find('title')
            title = title.get_text().strip() if title else None

            return title, text_content, markdown_content
        except Exception as e:
            print(f"TrafilaturaEnhanced error: {e}")
            return None, None, None


class NewspaperMethod(ExtractionMethod):
    """Newspaper3k extraction method."""

    def __init__(self):
        super().__init__("Newspaper3k")

    def extract(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        try:
            article = Article(url)
            article.download()
            article.parse()

            # Convert text to markdown using html2text
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.body_width = 0  # No line wrapping

            # Create basic markdown from text
            markdown = h.handle(f"# {article.title}\n\n{article.text}")

            return article.title, article.text, markdown
        except Exception as e:
            print(f"Newspaper error: {e}")
            return None, None, None


class ReadabilityMethod(ExtractionMethod):
    """Python-readability extraction method."""

    def __init__(self):
        super().__init__("Python-Readability")

    def extract(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            # Use python-readability's parse function
            result = parse(response.text)
            title = result['title'] if result else None
            html_content = result['content'] if result else ""

            if not html_content:
                return title, None, None

            # Convert HTML to text and markdown
            soup = BeautifulSoup(html_content, 'html.parser')
            text_content = soup.get_text(separator='\n', strip=True)

            # Convert to markdown
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.body_width = 0
            markdown_content = h.handle(html_content)

            return title, text_content, markdown_content
        except Exception as e:
            print(f"Readability error: {e}")
            return None, None, None


class Html2TextMethod(ExtractionMethod):
    """Html2text with BeautifulSoup for better markdown."""

    def __init__(self):
        super().__init__("BeautifulSoup + Html2Text")

    def extract(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract title
            title_tag = soup.find('title')
            title = title_tag.get_text().strip() if title_tag else None

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                script.decompose()

            # Try to find main content area
            content = None
            for selector in ['article', '[role="main"]', 'main', '.content', '#content']:
                content = soup.select_one(selector)
                if content:
                    break

            if not content:
                content = soup.find('body')

            if not content:
                content = soup

            # Convert to text and markdown
            text_content = content.get_text(separator='\n', strip=True)

            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.body_width = 0
            h.ignore_emphasis = False
            markdown_content = h.handle(str(content))

            return title, text_content, markdown_content
        except Exception as e:
            print(f"Html2Text error: {e}")
            return None, None, None


def calculate_quality_metrics(title: Optional[str], text: Optional[str], markdown: Optional[str]) -> Dict[str, any]:
    """Calculate quality metrics for extracted content."""
    metrics = {}

    # Basic metrics
    metrics['has_title'] = title is not None and len(title.strip()) > 0
    metrics['text_length'] = len(text) if text else 0
    metrics['markdown_length'] = len(markdown) if markdown else 0

    if text:
        # Count lines and paragraphs
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        metrics['line_count'] = len(lines)
        metrics['avg_line_length'] = sum(len(line) for line in lines) / len(lines) if lines else 0

        # Count potential ads/navigation (lines with common ad keywords)
        ad_keywords = ['advertisement', 'sponsored', 'subscribe', 'newsletter', 'cookie', 'privacy policy', 'terms of service']
        ad_lines = sum(1 for line in lines if any(keyword.lower() in line.lower() for keyword in ad_keywords))
        metrics['potential_ad_lines'] = ad_lines
        metrics['ad_ratio'] = ad_lines / len(lines) if lines else 0

    if markdown:
        # Markdown-specific metrics
        metrics['markdown_headers'] = len(re.findall(r'^#+\s', markdown, re.MULTILINE))
        metrics['markdown_links'] = len(re.findall(r'\[.*?\]\(.*?\)', markdown))
        metrics['markdown_bold'] = len(re.findall(r'\*\*.*?\*\*', markdown))
        metrics['markdown_italic'] = len(re.findall(r'\*.*?\*', markdown))
        metrics['markdown_code'] = len(re.findall(r'`.*?`', markdown))

    return metrics


def save_comparison_results(url: str, results: List[Tuple[ExtractionMethod, Tuple, Dict]], output_dir: Path):
    """Save formatted comparison results to files."""
    # Create URL-safe filename
    import re
    safe_url = re.sub(r'[^\w\-_.]', '_', url.replace('://', '_').replace('/', '_'))
    url_dir = output_dir / safe_url
    url_dir.mkdir(parents=True, exist_ok=True)

    # Create summary report
    summary_content = []
    summary_content.append(f"# EXTRACTION COMPARISON RESULTS")
    summary_content.append(f"**URL:** {url}")
    summary_content.append(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    summary_content.append("")

    # Summary table
    summary_content.append("## Summary Table")
    summary_content.append("")
    summary_content.append("| Method | Text Length | Lines | Avg Line | Ad Lines | MD Headers | MD Links | Time |")
    summary_content.append("|--------|-------------|-------|----------|----------|------------|----------|------|")

    for i, (method, (title, text, markdown), metrics) in enumerate(results):
        if 'error' in metrics:
            summary_content.append(f"| {method.name} | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR | ERROR |")
        else:
            summary_content.append(f"| {method.name} | {metrics.get('text_length', 0):,} | {metrics.get('line_count', 0)} | {metrics.get('avg_line_length', 0):.1f} | {metrics.get('potential_ad_lines', 0)} | {metrics.get('markdown_headers', 0)} | {metrics.get('markdown_links', 0)} | {metrics.get('extraction_time', 0):.2f}s |")

    summary_content.append("")

    # Detailed results for each method
    for i, (method, (title, text, markdown), metrics) in enumerate(results):
        summary_content.append(f"## METHOD {i+1}: {method.name}")
        summary_content.append("")

        # Title
        summary_content.append(f"**Title:** {title or 'None'}")
        summary_content.append("")

        # Metrics
        if 'error' in metrics:
            summary_content.append(f"**Error:** {metrics['error']}")
        else:
            summary_content.append("**Metrics:**")
            summary_content.append(f"- Text Length: {metrics.get('text_length', 0):,} chars")
            summary_content.append(f"- Lines: {metrics.get('line_count', 0)}")
            summary_content.append(f"- Avg Line Length: {metrics.get('avg_line_length', 0):.1f} chars")
            summary_content.append(f"- Potential Ad Lines: {metrics.get('potential_ad_lines', 0)} ({metrics.get('ad_ratio', 0):.1%})")
            summary_content.append(f"- MD Headers: {metrics.get('markdown_headers', 0)}")
            summary_content.append(f"- MD Links: {metrics.get('markdown_links', 0)}")
            summary_content.append(f"- MD Formatting: {metrics.get('markdown_bold', 0)} bold, {metrics.get('markdown_italic', 0)} italic")
            summary_content.append(f"- Extraction Time: {metrics.get('extraction_time', 0):.2f}s")

        summary_content.append("")

        # Save full content to individual files
        method_safe_name = re.sub(r'[^\w\-_.]', '_', method.name)

        # Save full text
        if text:
            text_file = url_dir / f"{i+1:02d}_{method_safe_name}_text.txt"
            text_file.write_text(text, encoding='utf-8')
            summary_content.append(f"**Full Text:** [📄 {text_file.name}]({text_file.name})")
        else:
            summary_content.append("**Full Text:** None")

        # Save full markdown
        if markdown:
            md_file = url_dir / f"{i+1:02d}_{method_safe_name}_markdown.md"
            md_file.write_text(markdown, encoding='utf-8')
            summary_content.append(f"**Full Markdown:** [📝 {md_file.name}]({md_file.name})")
        else:
            summary_content.append("**Full Markdown:** None")

        # Content previews in summary
        summary_content.append("")
        summary_content.append("**Text Preview (first 500 chars):**")
        text_preview = text[:500] + "..." if text and len(text) > 500 else (text or "None")
        summary_content.append("```")
        summary_content.append(text_preview)
        summary_content.append("```")
        summary_content.append("")

        summary_content.append("**Markdown Preview (first 500 chars):**")
        md_preview = markdown[:500] + "..." if markdown and len(markdown) > 500 else (markdown or "None")
        summary_content.append("```markdown")
        summary_content.append(md_preview)
        summary_content.append("```")
        summary_content.append("")
        summary_content.append("---")
        summary_content.append("")

    # Save summary report
    summary_file = url_dir / "00_SUMMARY.md"
    summary_file.write_text("\n".join(summary_content), encoding='utf-8')

    # Print console output for immediate feedback
    print(f"\n✅ Results saved to: {url_dir}")
    print(f"📋 Summary report: {summary_file}")
    print(f"📁 Individual files: {len([f for f in url_dir.glob('*') if f.name != '00_SUMMARY.md'])} files")


def print_comparison_results(url: str, results: List[Tuple[ExtractionMethod, Tuple, Dict]]):
    """Print formatted comparison results to console (shortened version)."""
    print(f"\n{'='*80}")
    print(f"EXTRACTION COMPARISON RESULTS")
    print(f"URL: {url}")
    print(f"{'='*80}")

    # Quick summary table
    print(f"\n{'Method':<25} {'Text Length':<12} {'MD Links':<10} {'Time':<8}")
    print(f"{'-'*25} {'-'*12} {'-'*10} {'-'*8}")

    for method, (title, text, markdown), metrics in results:
        if 'error' in metrics:
            print(f"{method.name:<25} {'ERROR':<12} {'ERROR':<10} {'ERROR':<8}")
        else:
            text_len = f"{metrics.get('text_length', 0):,}"[:11]
            md_links = str(metrics.get('markdown_links', 0))
            time_str = f"{metrics.get('extraction_time', 0):.2f}s"
            print(f"{method.name:<25} {text_len:<12} {md_links:<10} {time_str:<8}")

    print(f"\n💾 Full results saved to output files (see above)")
    print(f"🔍 Check individual text/markdown files for detailed comparison")


async def run_extraction_comparison():
    """Run the extraction comparison test."""

    # Create output directory
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    print(f"📁 Output directory: {output_dir.absolute()}")
    print("🔄 Starting extraction comparison test...")

    # Test URLs - variety of content types
    test_urls = [
        # Documentation
        "https://docs.python.org/3/tutorial/introduction.html",
        # Simple blog example
        "https://github.com/blog/2013-01-09-test-blog-post",
        # Wikipedia article
        "https://en.wikipedia.org/wiki/Web_scraping",
    ]

    # Initialize extraction methods
    methods = [
        CurrentMethod(),
        TrafilaturaEnhanced(favor_precision=True),
        TrafilaturaEnhanced(favor_precision=False),
        NewspaperMethod(),
        ReadabilityMethod(),
        Html2TextMethod(),
    ]

    # Test each URL with each method
    for url_idx, url in enumerate(test_urls):
        print(f"\n{'='*80}")
        print(f"TESTING URL {url_idx + 1}/{len(test_urls)}")
        print(f"{'='*80}")
        print(f"URL: {url}")

        results = []

        for method_idx, method in enumerate(methods):
            print(f"\nTesting method {method_idx + 1}/{len(methods)}: {method.name}...")

            start_time = time.time()
            try:
                if isinstance(method, CurrentMethod):
                    title, text, markdown = await method.extract(url)
                else:
                    title, text, markdown = method.extract(url)

                end_time = time.time()

                # Calculate metrics
                metrics = calculate_quality_metrics(title, text, markdown)
                metrics['extraction_time'] = end_time - start_time

                results.append((method, (title, text, markdown), metrics))
                print(f"  ✓ Success ({metrics['extraction_time']:.2f}s)")

            except Exception as e:
                print(f"  ✗ Failed: {e}")
                results.append((method, (None, None, None), {'error': str(e)}))

        # Save and print comparison for this URL
        save_comparison_results(url, results, output_dir)
        print_comparison_results(url, results)

        # Wait between URLs to be respectful
        if url_idx < len(test_urls) - 1:
            print(f"\n\nWaiting 3 seconds before next URL...")
            await asyncio.sleep(3)

    print(f"\n{'='*80}")
    print("EXTRACTION COMPARISON COMPLETE")
    print(f"{'='*80}")
    print("\nReview the results above to determine which extraction method")
    print("produces the cleanest text and best formatted markdown.")
    print("\nConsider factors like:")
    print("- Content cleanliness (fewer ads/navigation)")
    print("- Markdown formatting quality")
    print("- Extraction accuracy and completeness")
    print("- Performance (extraction time)")


if __name__ == "__main__":
    asyncio.run(run_extraction_comparison())
