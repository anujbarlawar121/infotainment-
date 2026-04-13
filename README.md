# AI-Powered Personalized News & Entertainment Hub

A full-stack Flask web application that combines personalized news, movie, music, video, meme discovery, analytics dashboards, sentiment analysis, visitor logging, and admin tooling.

## Stack

- Frontend: HTML, CSS, Bootstrap 5, JavaScript, Chart.js
- Backend: Python Flask
- Database: SQLite by default
- ML/NLP: Scikit-learn hybrid models for recommendations and sentiment
- Live data: Google News RSS, curated news/movie/music feeds, Apple RSS, YouTube channel feeds, Reddit feeds, Imgflip
- Optional premium APIs: News API, YouTube Data API, Spotify API, TMDb API

## Features

- User signup, login, logout, and session-based access control
- Form security hardening with CSRF protection and stricter input validation
- Home page with live category cards for news, movies, songs, videos, and memes
- Multi-domain live data aggregation (Google News + curated news feeds, Apple charts, YouTube feeds, Reddit meme feeds, and more)
- Hybrid recommendation engine (semantic similarity + interest overlap + mood/category alignment + freshness + source quality)
- Hybrid sentiment engine (lexical context rules + ML classifier for better edge-case handling)
- Trending dashboard with chart visualizations and KPI cards
- Visitor logging with browser, device, IP, viewed category, and login time
- Dedicated DBMS audit tables for login history (success + failures) and content interactions (clicks + recommendation impressions)
- User-facing "My Login History" page for personal login audit trail
- Admin-only visitor logs page with filtering, pagination, and CSV export
- Admin-only login history page with filtering, pagination, and CSV export
- Recommendation refresh prioritizes the current mood + interests input immediately
- Contact form stored in the database
- Admin dashboard for users, messages, and visitor activity
- Health check endpoint at `/health` for deployment monitoring
- Responsive Bootstrap UI, dark mode toggle, notifications, search, and filters

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Then open:

- App: `http://127.0.0.1:5000`
- Health check: `http://127.0.0.1:5000/health`

## Render Deployment

This repo includes a ready Blueprint file: `render.yaml`.

1. Push this project to GitHub.
2. Open Render Blueprint deploy:
   `https://dashboard.render.com/blueprint/new?repo=https://github.com/<your-username>/<your-repo>`
3. Fill secret env vars (`SECRET_KEY` and any optional API keys).
4. Click **Apply**.

The Blueprint creates:
- Web service: `ai-hub-web` (Gunicorn)
- PostgreSQL database: `ai-hub-db`

Optional API keys:

```powershell
$env:NEWS_API_KEY="your_news_api_key"
$env:YOUTUBE_API_KEY="your_youtube_api_key"
$env:SPOTIFY_CLIENT_ID="your_spotify_client_id"
$env:SPOTIFY_CLIENT_SECRET="your_spotify_client_secret"
$env:TMDB_API_KEY="your_tmdb_api_key"
```

## Sample Accounts

- Admin: `admin@example.com` / `admin123`
- Demo User: `demo@example.com` / `demo123`

New signups now require:

- Password length >= 8
- At least one letter and one number

## Notes

- The SQLite database is created automatically in `instance/news_hub_app.db` by default.
- Sentiment scoring uses a hybrid lexical + ML model trained locally on startup.
- Without API keys, the app still uses real public feeds for news, songs, movies, videos, and memes.
- API failures fall back to the latest cached content and then to bundled sample content.
- New database tables are auto-created on startup: `login_history` and `content_interactions`.
- `schema.sql` contains the schema and `sample_data.sql` contains optional insert statements for manual seeding.
