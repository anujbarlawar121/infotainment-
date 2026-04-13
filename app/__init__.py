import os
from pathlib import Path

from flask import Flask

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RUNTIME_ROOT = (BASE_DIR / "instance").resolve()


def resolve_runtime_dir():
    configured = os.getenv("AI_HUB_RUNTIME_DIR", "").strip()
    candidates = [Path(configured).resolve()] if configured else []
    candidates.append(DEFAULT_RUNTIME_ROOT)

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue
    return candidates[-1]


RUNTIME_DIR = resolve_runtime_dir()
os.environ["AI_HUB_RUNTIME_DIR"] = str(RUNTIME_DIR)

from .models import db, seed_database
from .routes import main_bp


def resolve_database_url(default_db_path):
    configured = os.getenv("DATABASE_URL", "").strip()
    if not configured:
        return f"sqlite:///{default_db_path.as_posix()}"
    if configured.startswith("postgres://"):
        return configured.replace("postgres://", "postgresql://", 1)
    return configured


def create_app():
    default_db_path = (RUNTIME_DIR / "news_hub_app.db").resolve()
    app = Flask(
        __name__,
        instance_path=str(RUNTIME_DIR),
        template_folder=str(BASE_DIR / "app" / "templates"),
        static_folder=str(BASE_DIR / "app" / "static"),
    )

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = resolve_database_url(default_db_path)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    app.config["NEWS_API_KEY"] = os.getenv("NEWS_API_KEY", "")
    app.config["YOUTUBE_API_KEY"] = os.getenv("YOUTUBE_API_KEY", "")
    app.config["SPOTIFY_CLIENT_ID"] = os.getenv("SPOTIFY_CLIENT_ID", "")
    app.config["SPOTIFY_CLIENT_SECRET"] = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    app.config["TMDB_API_KEY"] = os.getenv("TMDB_API_KEY", "")

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(default_db_path.parent / "mplconfig", exist_ok=True)

    db.init_app(app)
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()
        seed_database()

    return app
