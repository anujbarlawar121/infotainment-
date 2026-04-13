import base64
import html
import json
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests
from flask import current_app


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RUNTIME_ROOT = (BASE_DIR / "instance").resolve()
RUNTIME_DIR = Path(os.getenv("AI_HUB_RUNTIME_DIR", str(DEFAULT_RUNTIME_ROOT))).resolve()
CACHE_DIR = RUNTIME_DIR / "content_cache"
DATA_FILE = BASE_DIR / "data" / "sample_content.json"
REQUEST_TIMEOUT = 15
REQUEST_HEADERS = {
    "User-Agent": "AIHub/1.0 (+https://localhost)",
    "Accept-Language": "en-US,en;q=0.9",
}
MEMORY_CACHE = {}

FALLBACK_IMAGES = {
    "News": "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=900&q=80",
    "Movies": "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=900&q=80",
    "Songs": "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?auto=format&fit=crop&w=900&q=80",
    "Videos": "https://images.unsplash.com/photo-1492619375914-88005aa9e8fb?auto=format&fit=crop&w=900&q=80",
    "Memes": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=900&q=80",
}

YOUTUBE_CHANNELS = [
    ("@TED", "TED"),
    ("@Netflix", "Netflix"),
    ("@FallonTonight", "The Tonight Show"),
    ("@PrimeVideo", "Prime Video"),
    ("@ESPN", "ESPN"),
    ("@FIFATV", "FIFA"),
]

NEWS_FEEDS = [
    ("https://feeds.bbci.co.uk/news/world/rss.xml", "BBC World"),
    ("https://feeds.bbci.co.uk/news/technology/rss.xml", "BBC Technology"),
    ("https://www.theverge.com/rss/index.xml", "The Verge"),
    ("https://feeds.arstechnica.com/arstechnica/index", "Ars Technica"),
    ("https://www.engadget.com/rss.xml", "Engadget"),
    ("https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "NYTimes Technology"),
    ("https://www.espn.com/espn/rss/news", "ESPN"),
]

MOVIE_FEEDS = [
    ("https://www.slashfilm.com/feed/", "SlashFilm"),
    ("https://collider.com/feed/", "Collider"),
    ("https://screenrant.com/feed/", "ScreenRant"),
]

MUSIC_FEEDS = [
    ("https://pitchfork.com/rss/news/", "Pitchfork"),
    ("https://www.billboard.com/feed/", "Billboard"),
]

VIDEO_FEEDS = [
    ("https://vimeo.com/channels/staffpicks/videos/rss", "Vimeo Staff Picks"),
    ("https://www.ign.com/rss", "IGN"),
]

MEME_FEEDS = [
    ("https://www.reddit.com/r/memes/hot/.rss", "Reddit r/memes"),
    ("https://www.reddit.com/r/dankmemes/hot/.rss", "Reddit r/dankmemes"),
]

CATEGORY_DESCRIPTIONS = {
    "news": "Live headlines aggregated from multiple trusted news domains.",
    "movies": "Movie charts and film coverage from live entertainment sources.",
    "songs": "Top tracks and music trends from streaming and music platforms.",
    "videos": "Fresh video picks from YouTube and leading media channels.",
    "memes": "Trending memes from live community and template platforms.",
}

GOOGLE_NEWS_QUERIES = [
    "technology OR entertainment OR movies OR music",
    "gaming OR esports OR streaming OR creator economy",
    "AI OR science OR startups OR innovation",
    "sports OR football OR cricket OR basketball",
]


@lru_cache(maxsize=1)
def load_sample_content():
    try:
        with DATA_FILE.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"news": [], "movies": [], "songs": [], "videos": [], "memes": []}


def _sample_items(content_key, category, limit):
    sample_items = load_sample_content().get(content_key, [])[:limit]
    return [
        _normalize_item(
            category,
            item.get("title", "Untitled"),
            item.get("description", "No description available."),
            item.get("url", "#"),
            item.get("image", ""),
            item.get("provider", "Sample Data"),
            item.get("published_at", ""),
        )
        for item in sample_items
    ]


def _ensure_cache_dir():
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def _cache_path(cache_key):
    _ensure_cache_dir()
    return CACHE_DIR / f"{cache_key}.json"


def _read_cache(cache_key):
    path = _cache_path(cache_key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(cache_key, data):
    payload = {"timestamp": time.time(), "data": data}
    MEMORY_CACHE[cache_key] = payload
    try:
        _cache_path(cache_key).write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass
    return data


def _get_cached_data(cache_key, loader, ttl_seconds=1800):
    cached = MEMORY_CACHE.get(cache_key) or _read_cache(cache_key)
    now = time.time()
    if cached and now - cached.get("timestamp", 0) < ttl_seconds:
        return cached.get("data", [])
    try:
        fresh = loader()
        if fresh:
            return _write_cache(cache_key, fresh)
    except Exception:
        pass
    if cached:
        return cached.get("data", [])
    return []


def _clean_text(value):
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    return html.unescape(" ".join(text.split()))


def _extract_image(raw_html, fallback_category):
    match = re.search(r'<img[^>]+src="([^"]+)"', raw_html or "", flags=re.IGNORECASE)
    if match:
        return html.unescape(match.group(1))
    return FALLBACK_IMAGES.get(fallback_category, "")


def _parse_datetime(raw_value):
    if not raw_value:
        return None
    value = raw_value.strip()
    if not value:
        return None
    try:
        if value.endswith("Z"):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            parsed = datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except Exception:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_date(raw_value):
    parsed = _parse_datetime(raw_value)
    if parsed:
        return parsed.strftime("%Y-%m-%d")
    return raw_value[:10] if raw_value else ""


def _local_domain(url):
    netloc = urlparse(url or "").netloc.lower().strip()
    return netloc[4:] if netloc.startswith("www.") else netloc


def _normalize_item(category, title, description, url, image="", provider="", published_at=""):
    clean_url = (url or "#").strip() or "#"
    return {
        "title": (title or "Untitled").strip(),
        "description": (description or "No description available.").strip(),
        "url": clean_url,
        "image": image or FALLBACK_IMAGES.get(category, ""),
        "category": category,
        "provider": provider or category,
        "published_at": _format_date(published_at),
        "domain": _local_domain(clean_url),
    }


def _dedupe_items(items, limit):
    deduped = []
    seen = set()
    for item in items:
        title_key = re.sub(r"\s+", " ", item.get("title", "").lower()).strip()
        key = (title_key, item.get("domain", ""), item.get("category", ""))
        if not title_key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _merge_source_items(sources, limit):
    merged = []
    for source_items in sources:
        if source_items:
            merged.extend(source_items)
    return _dedupe_items(merged, limit)


def _try_loader(loader):
    try:
        return loader() or []
    except Exception:
        return []


def _itunes_link(entry):
    link = entry.get("link", {})
    if isinstance(link, list):
        for candidate in link:
            href = candidate.get("attributes", {}).get("href", "")
            if href:
                return href
    return link.get("attributes", {}).get("href", "#")


def _itunes_image(entry, category):
    images = entry.get("im:image", [])
    if isinstance(images, list) and images:
        return images[-1].get("label", "")
    return FALLBACK_IMAGES[category]


def _split_news_title(raw_title):
    title, separator, source = raw_title.rpartition(" - ")
    if separator and source:
        return title, source
    return raw_title, "Google News"


def _safe_get(url, **kwargs):
    headers = {**REQUEST_HEADERS, **kwargs.pop("headers", {})}
    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)
    response.raise_for_status()
    return response


def _safe_post(url, **kwargs):
    headers = {**REQUEST_HEADERS, **kwargs.pop("headers", {})}
    response = requests.post(url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)
    response.raise_for_status()
    return response


def _entry_fields(entry):
    values = {}
    for node in entry.iter():
        local_name = node.tag.split("}", 1)[-1].lower()
        if local_name not in values and (node.text or "").strip():
            values[local_name] = node.text.strip()
    return values


def _entry_link(entry):
    for node in entry.iter():
        local_name = node.tag.split("}", 1)[-1].lower()
        if local_name != "link":
            continue
        href = (node.attrib.get("href", "") or node.attrib.get("url", "")).strip()
        if href:
            return href
        text_value = (node.text or "").strip()
        if text_value.startswith("http"):
            return text_value
    return "#"


def _entry_image(entry, description, category):
    for node in entry.iter():
        local_name = node.tag.split("}", 1)[-1].lower()
        if local_name in {"thumbnail", "content", "enclosure"}:
            image_url = (
                node.attrib.get("url", "")
                or node.attrib.get("href", "")
                or node.attrib.get("{http://www.w3.org/1999/xlink}href", "")
            ).strip()
            if image_url:
                return image_url
    return _extract_image(description, category)


def _parse_feed_items(raw_content, category, provider, limit):
    root = ET.fromstring(raw_content)
    entries = root.findall(".//item")
    if not entries:
        entries = root.findall(".//{*}entry")

    items = []
    for entry in entries[:limit]:
        fields = _entry_fields(entry)
        title = fields.get("title", "Untitled")
        description = (
            fields.get("description")
            or fields.get("summary")
            or fields.get("content")
            or fields.get("encoded")
            or "No description available."
        )
        link = _entry_link(entry)
        published = fields.get("pubdate") or fields.get("published") or fields.get("updated") or fields.get("date", "")
        items.append(
            _normalize_item(
                category,
                title,
                _clean_text(description),
                link,
                _entry_image(entry, description, category),
                provider,
                published,
            )
        )
    return items


def _load_rss_sources(feed_specs, category, limit):
    items = []
    per_feed = max(2, (limit // max(len(feed_specs), 1)) + 1)
    for feed_url, provider in feed_specs:
        try:
            response = _safe_get(feed_url)
            items.extend(_parse_feed_items(response.content, category, provider, per_feed))
        except Exception:
            continue
    return items


def _spotify_token():
    client_id = current_app.config.get("SPOTIFY_CLIENT_ID")
    client_secret = current_app.config.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        return ""

    encoded = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
    response = _safe_post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {encoded}"},
        data={"grant_type": "client_credentials"},
    )
    return response.json().get("access_token", "")


def _load_newsapi(limit):
    response = _safe_get(
        "https://newsapi.org/v2/top-headlines",
        params={
            "country": "us",
            "pageSize": limit,
            "category": "general",
            "apiKey": current_app.config.get("NEWS_API_KEY"),
        },
    )
    return [
        _normalize_item(
            "News",
            item.get("title", "Untitled story"),
            item.get("description", "No description available."),
            item.get("url", "#"),
            item.get("urlToImage", ""),
            item.get("source", {}).get("name", "News API"),
            item.get("publishedAt", ""),
        )
        for item in response.json().get("articles", [])[:limit]
    ]


def _load_google_news_query(query, limit):
    response = _safe_get(
        "https://news.google.com/rss/search",
        params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
    )
    root = ET.fromstring(response.content)
    items = []
    for entry in root.findall(".//item")[:limit]:
        raw_title = entry.findtext("title", default="")
        title, provider = _split_news_title(raw_title)
        raw_description = entry.findtext("description", default="")
        items.append(
            _normalize_item(
                "News",
                title,
                _clean_text(raw_description) or f"Latest coverage from {provider}.",
                entry.findtext("link", default="#"),
                _extract_image(raw_description, "News"),
                provider,
                entry.findtext("pubDate", default=""),
            )
        )
    return items


def _load_google_news(limit):
    per_query = max(2, (limit // len(GOOGLE_NEWS_QUERIES)) + 1)
    items = []
    for query in GOOGLE_NEWS_QUERIES:
        try:
            items.extend(_load_google_news_query(query, per_query))
        except Exception:
            continue
    return items


def _load_curated_news(limit):
    return _load_rss_sources(NEWS_FEEDS, "News", limit)


def get_news(limit=12):
    sample = _sample_items("news", "News", limit)

    def _loader():
        sources = []
        if current_app.config.get("NEWS_API_KEY"):
            sources.append(_try_loader(lambda: _load_newsapi(limit)))
        sources.append(_try_loader(lambda: _load_google_news(limit)))
        sources.append(_try_loader(lambda: _load_curated_news(limit)))
        return _merge_source_items(sources, limit)

    return _get_cached_data(f"news_v4_{limit}", _loader) or sample


def _load_tmdb_movies(limit):
    response = _safe_get(
        "https://api.themoviedb.org/3/trending/movie/week",
        params={"api_key": current_app.config.get("TMDB_API_KEY")},
    )
    return [
        _normalize_item(
            "Movies",
            item.get("title", "Untitled movie"),
            item.get("overview", "No overview available."),
            f"https://www.themoviedb.org/movie/{item['id']}",
            f"https://image.tmdb.org/t/p/w500{item['poster_path']}" if item.get("poster_path") else "",
            "TMDb",
            item.get("release_date", ""),
        )
        for item in response.json().get("results", [])[:limit]
    ]


def _load_itunes_top_movies(limit):
    response = _safe_get(f"https://itunes.apple.com/us/rss/topmovies/limit={limit}/json")
    entries = response.json().get("feed", {}).get("entry", [])
    if not isinstance(entries, list):
        entries = [entries]
    return [
        _normalize_item(
            "Movies",
            entry.get("im:name", {}).get("label", "Untitled movie"),
            entry.get("summary", {}).get("label", "No description available."),
            _itunes_link(entry),
            _itunes_image(entry, "Movies"),
            "Apple Movies",
            entry.get("im:releaseDate", {}).get("label", ""),
        )
        for entry in entries[:limit]
    ]


def _load_movie_news(limit):
    return _load_rss_sources(MOVIE_FEEDS, "Movies", limit)


def get_tmdb_movies(limit=12):
    sample = _sample_items("movies", "Movies", limit)

    def _loader():
        sources = []
        if current_app.config.get("TMDB_API_KEY"):
            sources.append(_try_loader(lambda: _load_tmdb_movies(limit)))
        sources.append(_try_loader(lambda: _load_itunes_top_movies(limit)))
        sources.append(_try_loader(lambda: _load_movie_news(limit)))
        return _merge_source_items(sources, limit)

    return _get_cached_data(f"movies_v4_{limit}", _loader) or sample


def _load_spotify_tracks(limit):
    token = _spotify_token()
    if not token:
        return []

    response = _safe_get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "top hits", "type": "track", "limit": limit},
    )
    return [
        _normalize_item(
            "Songs",
            item["name"],
            ", ".join(artist["name"] for artist in item["artists"]),
            item["external_urls"]["spotify"],
            item["album"]["images"][0]["url"] if item["album"]["images"] else "",
            "Spotify",
            item.get("album", {}).get("release_date", ""),
        )
        for item in response.json().get("tracks", {}).get("items", [])[:limit]
    ]


def _load_itunes_top_songs(limit):
    response = _safe_get(f"https://itunes.apple.com/us/rss/topsongs/limit={limit}/json")
    entries = response.json().get("feed", {}).get("entry", [])
    if not isinstance(entries, list):
        entries = [entries]
    return [
        _normalize_item(
            "Songs",
            entry.get("im:name", {}).get("label", "Untitled track"),
            entry.get("im:artist", {}).get("label", "Unknown artist"),
            _itunes_link(entry),
            _itunes_image(entry, "Songs"),
            "Apple Music",
            entry.get("im:releaseDate", {}).get("label", ""),
        )
        for entry in entries[:limit]
    ]


def _load_deezer_tracks(limit):
    response = _safe_get(f"https://api.deezer.com/chart/0/tracks?limit={limit}")
    data = response.json().get("data", [])
    return [
        _normalize_item(
            "Songs",
            item.get("title", "Untitled track"),
            item.get("artist", {}).get("name", "Unknown artist"),
            item.get("link", "#"),
            item.get("album", {}).get("cover_xl") or item.get("album", {}).get("cover_big", ""),
            "Deezer",
            "",
        )
        for item in data[:limit]
    ]


def _load_music_news(limit):
    return _load_rss_sources(MUSIC_FEEDS, "Songs", limit)


def get_spotify_tracks(limit=12):
    sample = _sample_items("songs", "Songs", limit)

    def _loader():
        sources = []
        if current_app.config.get("SPOTIFY_CLIENT_ID") and current_app.config.get("SPOTIFY_CLIENT_SECRET"):
            sources.append(_try_loader(lambda: _load_spotify_tracks(limit)))
        sources.append(_try_loader(lambda: _load_deezer_tracks(limit)))
        sources.append(_try_loader(lambda: _load_itunes_top_songs(limit)))
        sources.append(_try_loader(lambda: _load_music_news(limit)))
        return _merge_source_items(sources, limit)

    return _get_cached_data(f"songs_v4_{limit}", _loader) or sample


def _load_youtube_api(limit):
    response = _safe_get(
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "part": "snippet",
            "q": "trending entertainment",
            "type": "video",
            "maxResults": limit,
            "key": current_app.config.get("YOUTUBE_API_KEY"),
        },
    )
    return [
        _normalize_item(
            "Videos",
            item["snippet"]["title"],
            item["snippet"]["description"],
            f"https://www.youtube.com/watch?v={item['id']['videoId']}",
            item["snippet"]["thumbnails"]["high"]["url"],
            item["snippet"].get("channelTitle", "YouTube"),
            item["snippet"].get("publishedAt", ""),
        )
        for item in response.json().get("items", [])[:limit]
    ]


def _resolve_youtube_channel_id(handle):
    response = _safe_get(f"https://www.youtube.com/{handle}")
    match = re.search(r'"channelId":"(UC[^"]+)"', response.text)
    return match.group(1) if match else ""


def _load_youtube_channel_feeds(limit):
    namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
        "media": "http://search.yahoo.com/mrss/",
    }
    items = []
    per_channel = max(limit // len(YOUTUBE_CHANNELS), 1)

    for handle, label in YOUTUBE_CHANNELS:
        channel_id = _resolve_youtube_channel_id(handle)
        if not channel_id:
            continue
        response = _safe_get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")
        root = ET.fromstring(response.content)

        for entry in root.findall("atom:entry", namespaces)[:per_channel]:
            media_thumbnail = entry.find(".//media:thumbnail", namespaces)
            media_description = entry.findtext(".//media:description", default="", namespaces=namespaces)
            published_at = entry.findtext("atom:published", default="", namespaces=namespaces)
            link_node = entry.find("atom:link", namespaces)
            items.append(
                _normalize_item(
                    "Videos",
                    entry.findtext("atom:title", default="Untitled video", namespaces=namespaces),
                    media_description or f"Latest upload from {label}.",
                    link_node.attrib.get("href", "#") if link_node is not None else "#",
                    media_thumbnail.attrib.get("url", "") if media_thumbnail is not None else "",
                    entry.findtext("atom:author/atom:name", default=label, namespaces=namespaces),
                    published_at,
                )
            )
    return items


def _load_video_feeds(limit):
    return _load_rss_sources(VIDEO_FEEDS, "Videos", limit)


def get_youtube_videos(limit=12):
    sample = _sample_items("videos", "Videos", limit)

    def _loader():
        sources = []
        if current_app.config.get("YOUTUBE_API_KEY"):
            sources.append(_try_loader(lambda: _load_youtube_api(limit)))
        sources.append(_try_loader(lambda: _load_youtube_channel_feeds(limit)))
        sources.append(_try_loader(lambda: _load_video_feeds(limit)))
        return _merge_source_items(sources, limit)

    return _get_cached_data(f"videos_v4_{limit}", _loader, ttl_seconds=3600) or sample


def _load_imgflip_memes(limit):
    response = _safe_get("https://api.imgflip.com/get_memes")
    memes = response.json().get("data", {}).get("memes", [])
    return [
        _normalize_item(
            "Memes",
            meme.get("name", "Trending meme"),
            f"Popular meme template with {meme.get('box_count', 0)} text boxes.",
            f"https://imgflip.com/memetemplate/{meme.get('id')}",
            meme.get("url", ""),
            "Imgflip",
            "",
        )
        for meme in memes[:limit]
    ]


def _load_reddit_memes(limit):
    return _load_rss_sources(MEME_FEEDS, "Memes", limit)


def get_memes(limit=12):
    sample = _sample_items("memes", "Memes", limit)

    def _loader():
        sources = [_try_loader(lambda: _load_imgflip_memes(limit)), _try_loader(lambda: _load_reddit_memes(limit))]
        return _merge_source_items(sources, limit)

    return _get_cached_data(f"memes_v4_{limit}", _loader, ttl_seconds=3600) or sample


def get_content_collections(limit=12):
    return {
        "news": get_news(limit),
        "movies": get_tmdb_movies(limit),
        "songs": get_spotify_tracks(limit),
        "videos": get_youtube_videos(limit),
        "memes": get_memes(limit),
    }


def get_categories(collections=None):
    collections = collections or get_content_collections(limit=12)
    title_map = {
        "news": "Breaking News",
        "movies": "Movies",
        "songs": "Songs",
        "videos": "Videos",
        "memes": "Memes",
    }
    return [
        {
            "title": title_map[key],
            "slug": key,
            "count": len(value),
            "description": CATEGORY_DESCRIPTIONS[key],
        }
        for key, value in collections.items()
    ]
