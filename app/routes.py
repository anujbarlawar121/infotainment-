import math
import re
import secrets
import time
from functools import wraps

from flask import (
    Blueprint,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import or_

from .models import (
    ContentInteraction,
    ContactMessage,
    LoginHistory,
    RecommendationHistory,
    SearchHistory,
    User,
    UserPreference,
    VisitorLog,
    db,
)
from .recommendation import get_recommendations
from .services import get_categories, get_content_collections
from .utils import (
    build_dashboard_stats,
    export_login_history_to_csv,
    export_logs_to_csv,
    get_client_ip,
    parse_user_agent,
)


main_bp = Blueprint("main", __name__)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MOOD_OPTIONS = {"happy", "relaxed", "excited", "curious", "sad"}
CONTENT_CATEGORIES = {"news", "movies", "songs", "videos", "memes"}
INTERACTION_TYPES = {"click", "recommendation_generated"}
MAX_LOGIN_ATTEMPTS = 5
LOGIN_ATTEMPT_WINDOW_SECONDS = 15 * 60


def current_user():
    user_id = session.get("user_id")
    return User.query.get(user_id) if user_id else None


def generate_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(24)
        session["_csrf_token"] = token
    return token


def _current_session_id():
    session_id = session.get("session_id")
    if not session_id:
        session_id = secrets.token_hex(16)
        session["session_id"] = session_id
    return session_id


@main_bp.app_context_processor
def inject_template_context():
    return {"current_user": current_user(), "csrf_token": generate_csrf_token, "session_id": _current_session_id}


@main_bp.before_app_request
def validate_csrf():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if request.endpoint in {"main.health"}:
        return None

    session_token = session.get("_csrf_token")
    request_token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not session_token or not request_token or not secrets.compare_digest(session_token, request_token):
        if request.is_json:
            return jsonify({"error": "csrf_validation_failed"}), 400
        flash("Security validation failed. Please try again.", "danger")
        return redirect(request.referrer or url_for("main.home"))
    return None


def _is_valid_email(email):
    return bool(EMAIL_PATTERN.match(email or ""))


def _normalize_mood(mood):
    selected = (mood or "").strip().lower()
    return selected if selected in MOOD_OPTIONS else "curious"


def _clean_text(value, default="", max_length=255):
    cleaned = (value or "").strip()
    if not cleaned:
        cleaned = default
    return cleaned[:max_length]


def _active_login_attempts():
    now = int(time.time())
    attempts = [stamp for stamp in session.get("login_attempts", []) if now - stamp <= LOGIN_ATTEMPT_WINDOW_SECONDS]
    session["login_attempts"] = attempts
    return attempts


def _record_failed_login():
    attempts = _active_login_attempts()
    attempts.append(int(time.time()))
    session["login_attempts"] = attempts


def _clear_failed_logins():
    session.pop("login_attempts", None)


def _record_login_event(email, status, failure_reason="", user=None):
    browser, device = parse_user_agent()
    try:
        db.session.add(
            LoginHistory(
                user_id=user.id if user else None,
                attempted_email=_clean_text(email, default="unknown@example.com", max_length=120).lower(),
                status=status,
                failure_reason=_clean_text(failure_reason, default="", max_length=255),
                browser=browser,
                device=device,
                ip_address=get_client_ip(),
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()


def _record_recommendation_impressions(user, mood, interests, recommendations, source_page):
    if not recommendations:
        return

    session_id = _current_session_id()
    entries = []
    for item in recommendations:
        entries.append(
            ContentInteraction(
                user_id=user.id if user else None,
                session_id=session_id,
                interaction_type="recommendation_generated",
                source_page=source_page,
                mood=mood,
                interests=interests,
                category=_clean_text(item.get("category"), default="unknown", max_length=50),
                title=_clean_text(item.get("title"), default="Untitled", max_length=255),
                provider=_clean_text(item.get("provider"), default="", max_length=120),
                domain=_clean_text(item.get("domain"), default="", max_length=120),
                content_url=_clean_text(item.get("url"), default="#", max_length=500),
                score=float(item.get("score", 0) or 0),
            )
        )

    try:
        db.session.add_all(entries)
        db.session.commit()
    except Exception:
        db.session.rollback()


def _build_personalized_interests(user):
    if not user:
        return ""

    search_terms = [
        entry.search_query
        for entry in SearchHistory.query.filter_by(user_id=user.id)
        .order_by(SearchHistory.searched_at.desc())
        .limit(8)
        .all()
    ]
    interaction_terms = [
        f"{entry.category} {entry.title} {entry.provider}"
        for entry in ContentInteraction.query.filter_by(user_id=user.id, interaction_type="click")
        .order_by(ContentInteraction.created_at.desc())
        .limit(10)
        .all()
    ]
    parts = [user.interests or ""] + search_terms + interaction_terms
    return ", ".join(part for part in parts if part)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please sign in to access that page.", "warning")
            return redirect(url_for("main.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            flash("Please sign in to access that page.", "warning")
            return redirect(url_for("main.login", next=request.path))
        if not user.is_admin:
            flash("Admin access is required for that page.", "danger")
            return redirect(url_for("main.home"))
        return view(*args, **kwargs)

    return wrapped


def log_visit(category):
    user = current_user()
    browser, device = parse_user_agent()
    name = user.name if user else "Guest User"
    email = user.email if user else "guest@example.com"
    try:
        db.session.add(
            VisitorLog(
                user_id=user.id if user else None,
                name=name,
                email=email,
                browser=browser,
                device=device,
                ip_address=get_client_ip(),
                category_viewed=category,
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()


@main_bp.route("/")
def home():
    user = current_user()
    query = request.args.get("q", "").strip()[:120]
    category_filter = request.args.get("category", "").strip().lower()
    if category_filter and category_filter not in CONTENT_CATEGORIES:
        category_filter = ""
    page = max(request.args.get("page", default=1, type=int), 1)
    per_page = 6

    collections = get_content_collections(limit=12)
    suggestions = []
    if user:
        suggestion_context = _build_personalized_interests(user)
        catalog_items = [item for group in collections.values() for item in group]
        suggestions = get_recommendations(
            user.preferred_mood,
            suggestion_context or user.interests,
            limit=5,
            catalog=catalog_items,
        )

    if query:
        db.session.add(
            SearchHistory(
                user_id=user.id if user else None,
                search_query=query,
                category=category_filter or "all",
            )
        )
        db.session.commit()

    filtered = {}
    for label, items in collections.items():
        if category_filter and label != category_filter:
            continue
        subset = [
            item
            for item in items
            if not query
            or query.lower() in item["title"].lower()
            or query.lower() in item["description"].lower()
        ]
        start = (page - 1) * per_page
        end = start + per_page
        filtered[label] = {"items": subset[start:end], "pages": max(math.ceil(len(subset) / per_page), 1)}

    log_visit(category_filter.title() if category_filter else "Home")
    return render_template(
        "home.html",
        collections=filtered,
        categories=get_categories(collections),
        suggestions=suggestions,
        query=query,
        selected_category=category_filter,
        page=page,
    )


@main_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = _clean_text(request.form.get("name"), max_length=120)
        email = _clean_text(request.form.get("email"), max_length=120).lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        preferred_mood = _normalize_mood(request.form.get("preferred_mood"))
        interests = _clean_text(request.form.get("interests"), default="", max_length=255)
        favorite_category = _clean_text(
            request.form.get("favorite_category"), default="News", max_length=120
        )
        favorite_artist = _clean_text(request.form.get("favorite_artist"), default="", max_length=120)
        favorite_topic = _clean_text(request.form.get("favorite_topic"), default="", max_length=120)

        errors = []
        if len(name) < 2:
            errors.append("Please enter your full name.")
        if not _is_valid_email(email):
            errors.append("Please enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
            errors.append("Password should include both letters and numbers.")
        if password != confirm_password:
            errors.append("Password and confirm password do not match.")

        if errors:
            for item in errors:
                flash(item, "warning")
            return redirect(url_for("main.signup"))

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
            return redirect(url_for("main.signup"))

        user = User(
            name=name,
            email=email,
            interests=interests,
            preferred_mood=preferred_mood,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        db.session.add(
            UserPreference(
                user_id=user.id,
                favorite_category=favorite_category,
                favorite_artist=favorite_artist,
                favorite_topic=favorite_topic,
            )
        )
        db.session.commit()
        flash("Account created successfully. Please sign in.", "success")
        return redirect(url_for("main.login"))

    return render_template("auth/signup.html")


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    attempts = _active_login_attempts()
    if request.method == "POST":
        email = _clean_text(request.form.get("email"), max_length=120).lower()

        if len(attempts) >= MAX_LOGIN_ATTEMPTS:
            _record_login_event(email, status="failed", failure_reason="rate_limited")
            flash("Too many failed login attempts. Please wait 15 minutes and try again.", "danger")
            return redirect(url_for("main.login"))

        password = request.form.get("password", "")
        if not _is_valid_email(email) or not password:
            _record_failed_login()
            _record_login_event(email, status="failed", failure_reason="invalid_input")
            flash("Please provide valid login credentials.", "danger")
            return redirect(url_for("main.login"))

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            _record_failed_login()
            _record_login_event(email, status="failed", failure_reason="invalid_credentials", user=user)
            flash("Invalid email or password.", "danger")
            return redirect(url_for("main.login"))

        _clear_failed_logins()
        session["user_id"] = user.id
        _current_session_id()
        _record_login_event(email, status="success", user=user)
        log_visit("Login")
        flash(f"Welcome back, {user.name}.", "success")
        next_url = request.args.get("next", "")
        if next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("main.home"))

    return render_template("auth/login.html")


@main_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))


@main_bp.route("/recommendations", methods=["GET", "POST"])
@login_required
def recommendations():
    user = current_user()
    is_post = request.method == "POST"
    mood = _normalize_mood(request.form.get("mood", user.preferred_mood))
    interests = _clean_text(request.form.get("interests", user.interests), max_length=255)
    history_context = _build_personalized_interests(user)

    # On manual refresh, prioritize exactly what user entered right now.
    ranking_interests = interests if is_post else ", ".join(part for part in [interests, history_context] if part)
    results = get_recommendations(mood, ranking_interests)

    if is_post:
        db.session.add(
            RecommendationHistory(
                user_id=user.id,
                mood=mood,
                interests=interests,
                recommended_titles=", ".join(item["title"] for item in results[:5]),
            )
        )
        user.preferred_mood = mood
        user.interests = interests
        db.session.commit()
        _record_recommendation_impressions(user, mood, interests, results[:8], source_page="recommendations")
        flash("Recommendations refreshed based on your mood and interests.", "success")

    log_visit("Recommendations")
    return render_template("recommendations.html", mood=mood, interests=interests, results=results)


@main_bp.route("/my-login-history")
@login_required
def my_login_history():
    user = current_user()
    page = max(request.args.get("page", default=1, type=int), 1)
    status_filter = request.args.get("status", "").strip().lower()

    query = LoginHistory.query.filter(
        or_(
            LoginHistory.user_id == user.id,
            LoginHistory.attempted_email == user.email,
        )
    ).order_by(LoginHistory.occurred_at.desc())

    if status_filter in {"success", "failed"}:
        query = query.filter(LoginHistory.status == status_filter)

    pagination = query.paginate(page=page, per_page=15, error_out=False)
    return render_template(
        "my_login_history.html",
        pagination=pagination,
        status_filter=status_filter,
    )


@main_bp.route("/sentiment", methods=["GET", "POST"])
def sentiment():
    analysis = None
    text = ""
    if request.method == "POST":
        from .nlp_service import analyze_sentiment

        text = request.form.get("text", "").strip()[:2000]
        if text:
            analysis = analyze_sentiment(text)
            flash("Sentiment analysis completed.", "success")
        else:
            flash("Please enter some text to analyze.", "warning")

    log_visit("Sentiment")
    return render_template("sentiment.html", analysis=analysis, text=text)


@main_bp.route("/trending")
def trending():
    collections = get_content_collections(limit=6)
    log_visit("Trending")
    return render_template(
        "trending.html",
        stats=build_dashboard_stats(),
        trends={key: value[:3] for key, value in collections.items() if key != "memes"},
    )


@main_bp.route("/visitor-logs")
@admin_required
def visitor_logs():
    term = request.args.get("q", "").strip()
    page = max(request.args.get("page", default=1, type=int), 1)

    query = VisitorLog.query.order_by(VisitorLog.login_time.desc())
    if term:
        like_term = f"%{term}%"
        query = query.filter(
            or_(
                VisitorLog.name.ilike(like_term),
                VisitorLog.email.ilike(like_term),
                VisitorLog.category_viewed.ilike(like_term),
                VisitorLog.browser.ilike(like_term),
            )
        )

    pagination = query.paginate(page=page, per_page=10, error_out=False)
    log_visit("Visitor Logs")
    return render_template("visitor_logs.html", pagination=pagination, term=term)


@main_bp.route("/visitor-logs/export")
@admin_required
def export_visitor_logs():
    logs = VisitorLog.query.order_by(VisitorLog.login_time.desc()).all()
    return Response(
        export_logs_to_csv(logs),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=visitor_logs.csv"},
    )


@main_bp.route("/login-history")
@admin_required
def login_history():
    term = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip().lower()
    page = max(request.args.get("page", default=1, type=int), 1)

    query = LoginHistory.query.order_by(LoginHistory.occurred_at.desc())
    if status_filter in {"success", "failed"}:
        query = query.filter(LoginHistory.status == status_filter)
    if term:
        like_term = f"%{term}%"
        query = query.filter(
            or_(
                LoginHistory.attempted_email.ilike(like_term),
                LoginHistory.ip_address.ilike(like_term),
                LoginHistory.browser.ilike(like_term),
                LoginHistory.device.ilike(like_term),
                LoginHistory.failure_reason.ilike(like_term),
            )
        )

    pagination = query.paginate(page=page, per_page=15, error_out=False)
    return render_template(
        "login_history.html",
        pagination=pagination,
        term=term,
        status_filter=status_filter,
    )


@main_bp.route("/login-history/export")
@admin_required
def export_login_history():
    events = LoginHistory.query.order_by(LoginHistory.occurred_at.desc()).all()
    return Response(
        export_login_history_to_csv(events),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=login_history.csv"},
    )


@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = _clean_text(request.form.get("name"), max_length=120)
        email = _clean_text(request.form.get("email"), max_length=120).lower()
        subject = _clean_text(request.form.get("subject"), max_length=150)
        message = _clean_text(request.form.get("message"), max_length=4000)

        if not name or not _is_valid_email(email) or len(subject) < 3 or len(message) < 10:
            flash("Please fill all fields correctly before submitting.", "warning")
            return redirect(url_for("main.contact"))

        db.session.add(
            ContactMessage(
                name=name,
                email=email,
                subject=subject,
                message=message,
            )
        )
        db.session.commit()
        flash("Your message has been sent successfully.", "success")
        return redirect(url_for("main.contact"))

    log_visit("Contact")
    return render_template("contact.html")


@main_bp.route("/admin")
@admin_required
def admin_dashboard():
    log_visit("Admin")
    return render_template(
        "admin/dashboard.html",
        stats=build_dashboard_stats(),
        users=User.query.order_by(User.created_at.desc()).limit(5).all(),
        messages=ContactMessage.query.order_by(ContactMessage.created_at.desc()).limit(5).all(),
        logs=VisitorLog.query.order_by(VisitorLog.login_time.desc()).limit(8).all(),
        login_events=LoginHistory.query.order_by(LoginHistory.occurred_at.desc()).limit(8).all(),
        interactions=ContentInteraction.query.order_by(ContentInteraction.created_at.desc()).limit(8).all(),
    )


@main_bp.route("/api/interactions", methods=["POST"])
def track_interactions():
    payload = request.get_json(silent=True) or {}
    interaction_type = _clean_text(payload.get("interaction_type"), default="click", max_length=40).lower()
    if interaction_type not in INTERACTION_TYPES:
        return jsonify({"error": "invalid_interaction_type"}), 400

    title = _clean_text(payload.get("title"), default="Untitled", max_length=255)
    category = _clean_text(payload.get("category"), default="unknown", max_length=50).lower()
    content_url = _clean_text(payload.get("url"), default="#", max_length=500)
    if content_url == "#":
        return jsonify({"error": "missing_url"}), 400

    user = current_user()
    session_id = _current_session_id()

    event = ContentInteraction(
        user_id=user.id if user else None,
        session_id=session_id,
        interaction_type=interaction_type,
        source_page=_clean_text(payload.get("source_page"), default="", max_length=60),
        mood=_clean_text(payload.get("mood"), default="", max_length=50),
        interests=_clean_text(payload.get("interests"), default="", max_length=255),
        category=category,
        title=title,
        provider=_clean_text(payload.get("provider"), default="", max_length=120),
        domain=_clean_text(payload.get("domain"), default="", max_length=120),
        content_url=content_url,
        score=float(payload.get("score", 0) or 0),
    )

    try:
        db.session.add(event)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "db_write_failed"}), 500

    return jsonify({"status": "ok"}), 200


@main_bp.route("/health")
def health():
    status = "ok"
    database = "up"
    code = 200
    try:
        User.query.limit(1).all()
    except Exception:
        db.session.rollback()
        status = "degraded"
        database = "down"
        code = 503
    return jsonify({"status": status, "database": database}), code


@main_bp.app_errorhandler(404)
def not_found(_error):
    return render_template("errors/404.html"), 404


@main_bp.app_errorhandler(500)
def server_error(_error):
    db.session.rollback()
    return render_template("errors/500.html"), 500
