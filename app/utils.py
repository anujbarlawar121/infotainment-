from collections import Counter
from io import StringIO

import csv
from flask import request

from .models import ContentInteraction, ContactMessage, LoginHistory, SearchHistory, User, VisitorLog


def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


def parse_user_agent():
    user_agent = request.headers.get("User-Agent", "Unknown Browser")
    browser = "Unknown Browser"
    device = "Desktop"
    for known in ["Chrome", "Firefox", "Safari", "Edge", "Opera"]:
        if known.lower() in user_agent.lower():
            browser = known
            break
    if any(keyword in user_agent.lower() for keyword in ["mobile", "android", "iphone"]):
        device = "Mobile"
    elif "ipad" in user_agent.lower() or "tablet" in user_agent.lower():
        device = "Tablet"
    return browser, device


def export_logs_to_csv(logs):
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Name", "Email", "Login Time", "Browser", "Device", "IP", "Category Viewed"])
    for log in logs:
        writer.writerow(
            [
                log.name,
                log.email,
                log.login_time.strftime("%Y-%m-%d %H:%M:%S"),
                log.browser,
                log.device,
                log.ip_address,
                log.category_viewed,
            ]
        )
    return buffer.getvalue()


def export_login_history_to_csv(events):
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Status", "Email", "User ID", "Time", "Browser", "Device", "IP", "Failure Reason"])
    for event in events:
        writer.writerow(
            [
                event.status,
                event.attempted_email,
                event.user_id or "",
                event.occurred_at.strftime("%Y-%m-%d %H:%M:%S"),
                event.browser,
                event.device,
                event.ip_address,
                event.failure_reason or "",
            ]
        )
    return buffer.getvalue()


def build_dashboard_stats():
    visitors = VisitorLog.query.all()
    searches = SearchHistory.query.all()
    login_events = LoginHistory.query.all()
    category_counter = Counter(log.category_viewed for log in visitors)
    search_counter = Counter(search.category for search in searches)
    login_counter = Counter(event.status for event in login_events)

    return {
        "user_count": User.query.count(),
        "message_count": ContactMessage.query.count(),
        "visitor_count": len(visitors),
        "search_count": len(searches),
        "interaction_count": ContentInteraction.query.count(),
        "login_success_count": login_counter.get("success", 0),
        "login_failed_count": login_counter.get("failed", 0),
        "category_labels": list(category_counter.keys()),
        "category_values": list(category_counter.values()),
        "search_labels": list(search_counter.keys()),
        "search_values": list(search_counter.values()),
    }
