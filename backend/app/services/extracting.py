"""Utilities for extracting data from webpages."""


from __future__ import annotations
import asyncio
from urllib.parse import urljoin, urlparse, urlunparse
import trafilatura
from datetime import datetime
from typing import Any
import re


def _build_favicon_url(parsed_url) -> str | None:
    if not parsed_url.scheme or not parsed_url.netloc:
        return None
    return urlunparse((parsed_url.scheme, parsed_url.netloc, "/favicon.ico", "", "", ""))


def _prepare_url(raw_url: str) -> str:
    if raw_url is None:
        raise ValueError("URL is required")

    candidate = raw_url.strip()
    if not candidate:
        raise ValueError("URL is required")

    if not candidate.startswith(("http://", "https://")):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Please enter a valid URL")

    # More robust URL validation
    # Check for valid domain format (basic validation)
    domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
    if not re.match(domain_pattern, parsed.netloc.split(':')[0]):
        raise ValueError("Please enter a valid URL with a proper domain")

    # Check for localhost and IP addresses (basic validation)
    netloc_host = parsed.netloc.split(':')[0]
    if netloc_host == 'localhost' or re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', netloc_host):
        # Allow localhost and IP addresses for development
        pass
    elif not re.match(domain_pattern, netloc_host):
        raise ValueError("Please enter a valid URL with a proper domain")
    elif '.' not in netloc_host:
        raise ValueError("Please enter a valid URL with a proper domain")

    return candidate


def _normalize_url(value: str | None, base: str) -> str | None:
    if not value:
        return None
    candidate = urljoin(base, value)
    parsed = urlparse(candidate)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return candidate
    return None


def _extract(raw_url: str) -> dict[str, Any] | None:
    url = _prepare_url(raw_url)

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None

    metadata = trafilatura.metadata.extract_metadata(downloaded)

    try:
        markdown_content = trafilatura.extract(
            downloaded,
            output_format="markdown",
            include_comments=False,
            include_tables=True,
            include_links=True,
            favor_precision=True,
            deduplicate=True,
        )
        text_content = trafilatura.extract(
            downloaded,
            output_format="txt",
            include_comments=False,
            include_tables=True,
            include_links=False,
            favor_precision=True,
            deduplicate=True,
        )

        # Check if extraction returned empty or meaningless content
        if not markdown_content or not text_content:
            raise ValueError("Extraction failed: No content could be extracted from the webpage.")

        # Check if content is just whitespace
        if not markdown_content.strip() or not text_content.strip():
            raise ValueError("Extraction failed: Only whitespace content found on the webpage.")

        # Check for minimum content length (at least 10 characters of meaningful content)
        if len(text_content.strip()) < 10:
            raise ValueError("Extraction failed: Insufficient content found on the webpage.")

    except Exception as e:
        if "Extraction failed:" in str(e):
            # Re-raise our custom extraction errors
            raise
        else:
            # Wrap other exceptions
            raise ValueError(f"Extraction failed with error: {str(e)}")

    canonical_url = _normalize_url(metadata.url, url) if metadata else None
    title = metadata.title if metadata else None
    source_site = metadata.sitename if metadata and metadata.sitename else None
    publication_date = metadata.date if metadata and metadata.date else None

    parsed = urlparse(canonical_url or url)
    favicon_url = _build_favicon_url(parsed)
    if not source_site and parsed.netloc:
        source_site = parsed.netloc


    extracted_at = datetime.now()

    return {
        "url": url,
        "canonical_url": canonical_url,
        "title": title,
        "source_site": source_site,
        "publication_date": publication_date,
        "favicon_url": favicon_url,
        "content_markdown": markdown_content,
        "content_text": text_content,
        "server_status": "extracted",
        "server_status_at": extracted_at,
    }


async def extract_data(url: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_extract, url)
