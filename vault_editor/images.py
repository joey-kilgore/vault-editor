from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

USER_AGENT = "vault-editor/0.1.0 (https://example.com; contact=local)"

WIKI_API = "https://commons.wikimedia.org/w/api.php"
OPEN_LIBRARY_SEARCH = "https://openlibrary.org/search.json"
OPEN_LIBRARY_COVER = "https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
OPEN_LIBRARY_COVER_ISBN = "https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
OPENAI_IMAGE_API = "https://api.openai.com/v1/images/generations"
TMDB_SEARCH_MOVIE = "https://api.themoviedb.org/3/search/movie"
TMDB_SEARCH_TV = "https://api.themoviedb.org/3/search/tv"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
TMDB_WATCH_PROVIDERS_MOVIE = "https://api.themoviedb.org/3/movie/{media_id}/watch/providers"
TMDB_WATCH_PROVIDERS_TV = "https://api.themoviedb.org/3/tv/{media_id}/watch/providers"


@dataclass(frozen=True)
class ImageResult:
    title: str
    url: str


def _sanitize_filename(name: str) -> str:
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9._-]", "", name)
    return name[:120] if name else "image"


def search_wikimedia(query: str) -> Optional[ImageResult]:
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": query,
        "srnamespace": 6,
        "srlimit": 1,
    }
    response = requests.get(
        WIKI_API, params=params, timeout=20, headers={"User-Agent": USER_AGENT}
    )
    response.raise_for_status()
    data = response.json()
    results = data.get("query", {}).get("search", [])
    if not results:
        return None

    title = results[0]["title"]
    info_params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url",
    }
    info_response = requests.get(
        WIKI_API, params=info_params, timeout=20, headers={"User-Agent": USER_AGENT}
    )
    info_response.raise_for_status()
    info_data = info_response.json()
    pages = info_data.get("query", {}).get("pages", {})
    for page in pages.values():
        imageinfo = page.get("imageinfo")
        if imageinfo:
            url = imageinfo[0].get("url")
            if url:
                return ImageResult(title=title, url=url)
    return None


def search_open_library_cover(query: str) -> Optional[ImageResult]:
    params = {
        "title": query,
        "limit": 1,
        "fields": "title,cover_i",
    }
    response = requests.get(
        OPEN_LIBRARY_SEARCH, params=params, timeout=20, headers={"User-Agent": USER_AGENT}
    )
    response.raise_for_status()
    data = response.json()
    docs = data.get("docs", [])
    if not docs:
        return None

    cover_id = docs[0].get("cover_i")
    title = docs[0].get("title") or query
    if not cover_id:
        return None

    url = OPEN_LIBRARY_COVER.format(cover_id=cover_id)
    return ImageResult(title=title, url=url)


def search_open_library_isbn(isbn: str) -> Optional[ImageResult]:
    isbn = re.sub(r"[^0-9Xx]", "", isbn)
    if not isbn:
        return None

    url = OPEN_LIBRARY_COVER_ISBN.format(isbn=isbn)
    try:
        response = requests.head(
            url, timeout=15, headers={"User-Agent": USER_AGENT}, allow_redirects=True
        )
        if response.status_code >= 400:
            return None
    except requests.RequestException:
        return None

    return ImageResult(title=f"ISBN {isbn}", url=url)


def search_open_library_isbn_by_title(
    title: str, author: Optional[str] = None
) -> Optional[str]:
    params = {
        "title": title,
        "limit": 5,
        "fields": "title,author_name,isbn",
    }
    if author:
        params["author"] = author

    response = requests.get(
        OPEN_LIBRARY_SEARCH, params=params, timeout=20, headers={"User-Agent": USER_AGENT}
    )
    response.raise_for_status()
    data = response.json()
    docs = data.get("docs", [])
    for doc in docs:
        isbns = doc.get("isbn") or []
        if not isbns:
            continue
        isbn13 = next((x for x in isbns if len(x) == 13), None)
        return isbn13 or isbns[0]
    return None


def _tmdb_headers(api_key: str) -> dict[str, str]:
    if api_key.startswith("ey"):
        return {"Authorization": f"Bearer {api_key}", "User-Agent": USER_AGENT}
    return {"User-Agent": USER_AGENT}


def _tmdb_search_first_result(
    endpoint: str, query: str, api_key: str
) -> Optional[dict]:
    if not api_key:
        return None

    params = {"query": query, "include_adult": "false", "language": "en-US"}
    if not api_key.startswith("ey"):
        params["api_key"] = api_key

    response = requests.get(
        endpoint,
        params=params,
        timeout=20,
        headers=_tmdb_headers(api_key),
    )
    response.raise_for_status()
    data = response.json()
    results = data.get("results", [])
    if not results:
        return None
    return results[0]


def search_tmdb_poster(query: str, api_key: str) -> Optional[ImageResult]:
    result = _tmdb_search_first_result(TMDB_SEARCH_MOVIE, query, api_key)
    if not result:
        return None

    poster_path = result.get("poster_path")
    title = result.get("title") or query
    if not poster_path:
        return None

    url = f"{TMDB_IMAGE_BASE}{poster_path}"
    return ImageResult(title=title, url=url)


def search_tmdb_tv_poster(query: str, api_key: str) -> Optional[ImageResult]:
    result = _tmdb_search_first_result(TMDB_SEARCH_TV, query, api_key)
    if not result:
        return None

    poster_path = result.get("poster_path")
    title = result.get("name") or query
    if not poster_path:
        return None

    url = f"{TMDB_IMAGE_BASE}{poster_path}"
    return ImageResult(title=title, url=url)


def search_tmdb_movie_id(query: str, api_key: str) -> Optional[int]:
    result = _tmdb_search_first_result(TMDB_SEARCH_MOVIE, query, api_key)
    if not result:
        return None
    return result.get("id")


def search_tmdb_tv_id(query: str, api_key: str) -> Optional[int]:
    result = _tmdb_search_first_result(TMDB_SEARCH_TV, query, api_key)
    if not result:
        return None
    return result.get("id")


def get_tmdb_watch_providers(
    media_type: str, media_id: int, api_key: str, region: str
) -> list[str]:
    if not api_key:
        return []

    endpoint = (
        TMDB_WATCH_PROVIDERS_MOVIE if media_type == "movie" else TMDB_WATCH_PROVIDERS_TV
    )
    url = endpoint.format(media_id=media_id)
    params = {}
    if not api_key.startswith("ey"):
        params["api_key"] = api_key

    response = requests.get(
        url,
        params=params,
        timeout=20,
        headers=_tmdb_headers(api_key),
    )
    response.raise_for_status()
    data = response.json()
    results = data.get("results", {})
    region_data = results.get(region.upper()) or {}

    providers: list[str] = []
    for key in ("flatrate", "free", "ads", "rent", "buy"):
        for item in region_data.get(key, []) or []:
            name = item.get("provider_name")
            if name and name not in providers:
                providers.append(name)
    return providers


def generate_openai_image(prompt: str, api_key: str, dest_dir: Path) -> Path:
    if not api_key:
        raise ValueError("OpenAI API key is missing.")

    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = _sanitize_filename(prompt)[:80]
    if not filename:
        filename = "openai_image"
    target = dest_dir / f"{filename}.png"

    payload = {
        "model": "gpt-image-1",
        "prompt": prompt,
        "size": "1024x1024",
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }

    response = requests.post(OPENAI_IMAGE_API, json=payload, timeout=60, headers=headers)
    if response.status_code >= 400:
        raise ValueError(
            f"OpenAI error {response.status_code}: {response.text.strip()}"
        )
    data = response.json()
    images = data.get("data", [])
    if not images:
        raise ValueError("OpenAI image generation returned no image data.")

    b64_json = images[0].get("b64_json")
    if b64_json:
        image_bytes = base64.b64decode(b64_json)
        with open(target, "wb") as f:
            f.write(image_bytes)
        return target

    url = images[0].get("url")
    if not url:
        raise ValueError("OpenAI image generation returned no usable image data.")

    with requests.get(url, stream=True, timeout=30, headers={"User-Agent": USER_AGENT}) as resp:
        resp.raise_for_status()
        with open(target, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)

    return target


def download_image(result: ImageResult, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = _sanitize_filename(Path(result.url).name)
    if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        filename = f"{filename}.jpg"

    target = dest_dir / filename
    if target.exists():
        return target

    with requests.get(
        result.url, stream=True, timeout=30, headers={"User-Agent": USER_AGENT}
    ) as resp:
        resp.raise_for_status()
        with open(target, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)
    return target
