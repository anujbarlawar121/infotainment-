from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class User(db.Model, TimestampMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    interests = db.Column(db.String(255), default="")
    preferred_mood = db.Column(db.String(50), default="curious")
    is_admin = db.Column(db.Boolean, default=False)

    preferences = db.relationship("UserPreference", backref="user", lazy=True)
    recommendations = db.relationship("RecommendationHistory", backref="user", lazy=True)
    searches = db.relationship("SearchHistory", backref="user", lazy=True)
    visitor_logs = db.relationship("VisitorLog", backref="user", lazy=True)
    login_events = db.relationship("LoginHistory", backref="user", lazy=True)
    interactions = db.relationship("ContentInteraction", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class VisitorLog(db.Model):
    __tablename__ = "visitor_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    login_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    browser = db.Column(db.String(120), nullable=False)
    device = db.Column(db.String(120), nullable=False)
    ip_address = db.Column(db.String(64), nullable=False)
    category_viewed = db.Column(db.String(120), nullable=False)


class ContactMessage(db.Model, TimestampMixin):
    __tablename__ = "contact_messages"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)


class RecommendationHistory(db.Model):
    __tablename__ = "recommendation_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    mood = db.Column(db.String(50), nullable=False)
    interests = db.Column(db.String(255), nullable=False)
    recommended_titles = db.Column(db.Text, nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class SearchHistory(db.Model):
    __tablename__ = "search_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    search_query = db.Column("query", db.String(255), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    searched_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class UserPreference(db.Model):
    __tablename__ = "user_preferences"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    favorite_category = db.Column(db.String(120), nullable=False)
    favorite_artist = db.Column(db.String(120), default="")
    favorite_topic = db.Column(db.String(120), default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LoginHistory(db.Model):
    __tablename__ = "login_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    attempted_email = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(20), nullable=False, index=True)
    failure_reason = db.Column(db.String(255), default="")
    browser = db.Column(db.String(120), nullable=False)
    device = db.Column(db.String(120), nullable=False)
    ip_address = db.Column(db.String(64), nullable=False, index=True)
    occurred_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)


class ContentInteraction(db.Model):
    __tablename__ = "content_interactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    session_id = db.Column(db.String(64), nullable=True, index=True)
    interaction_type = db.Column(db.String(40), nullable=False, index=True)
    source_page = db.Column(db.String(60), default="", nullable=False)
    mood = db.Column(db.String(50), default="")
    interests = db.Column(db.String(255), default="")
    category = db.Column(db.String(50), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    provider = db.Column(db.String(120), default="")
    domain = db.Column(db.String(120), default="", index=True)
    content_url = db.Column(db.String(500), nullable=False)
    score = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)


def seed_database():
    cleanup_placeholder_data()

    changed = False

    admin = User.query.filter_by(email="admin@example.com").first()
    if not admin:
        admin = User(
            name="Admin User",
            email="admin@example.com",
            interests="technology, movies, music, comedy",
            preferred_mood="excited",
            is_admin=True,
        )
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.flush()
        changed = True

    demo = User.query.filter_by(email="demo@example.com").first()
    if not demo:
        demo = User(
            name="Demo User",
            email="demo@example.com",
            interests="world news, anime, pop music, football",
            preferred_mood="relaxed",
            is_admin=False,
        )
        demo.set_password("demo123")
        db.session.add(demo)
        db.session.flush()
        changed = True

    if admin and not UserPreference.query.filter_by(user_id=admin.id).first():
        db.session.add(
            UserPreference(
                user_id=admin.id,
                favorite_category="Movies",
                favorite_artist="Hans Zimmer",
                favorite_topic="Startups",
            )
        )
        changed = True

    if demo and not UserPreference.query.filter_by(user_id=demo.id).first():
        db.session.add(
            UserPreference(
                user_id=demo.id,
                favorite_category="Music",
                favorite_artist="Coldplay",
                favorite_topic="AI",
            )
        )
        changed = True

    if changed:
        db.session.commit()


def cleanup_placeholder_data():
    ContactMessage.query.filter(ContactMessage.email.in_(["ava@example.com", "liam@example.com"])).delete(
        synchronize_session=False
    )
    SearchHistory.query.filter(
        SearchHistory.search_query.in_(
            ["AI startups", "feel good songs", "trending sci-fi films"]
        )
    ).delete(synchronize_session=False)
    RecommendationHistory.query.filter(
        RecommendationHistory.recommended_titles.in_(
            [
                "Future of AI Summit, Midnight City Playlist, Aurora Nights",
                "Startup Wave, Laugh Stream, Velocity Trailer Review",
            ]
        )
    ).delete(synchronize_session=False)
    VisitorLog.query.filter(
        VisitorLog.email.in_(["admin@example.com", "demo@example.com"]),
        VisitorLog.ip_address == "127.0.0.1",
        VisitorLog.category_viewed.in_(["Music", "News"]),
    ).delete(synchronize_session=False)
    db.session.commit()
