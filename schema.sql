CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    interests VARCHAR(255) DEFAULT '',
    preferred_mood VARCHAR(50) DEFAULT 'curious',
    is_admin BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE visitor_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(120) NOT NULL,
    login_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    browser VARCHAR(120) NOT NULL,
    device VARCHAR(120) NOT NULL,
    ip_address VARCHAR(64) NOT NULL,
    category_viewed VARCHAR(120) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE contact_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(120) NOT NULL,
    subject VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE recommendation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    mood VARCHAR(50) NOT NULL,
    interests VARCHAR(255) NOT NULL,
    recommended_titles TEXT NOT NULL,
    viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    query VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL,
    searched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    favorite_category VARCHAR(120) NOT NULL,
    favorite_artist VARCHAR(120) DEFAULT '',
    favorite_topic VARCHAR(120) DEFAULT '',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE login_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    attempted_email VARCHAR(120) NOT NULL,
    status VARCHAR(20) NOT NULL,
    failure_reason VARCHAR(255) DEFAULT '',
    browser VARCHAR(120) NOT NULL,
    device VARCHAR(120) NOT NULL,
    ip_address VARCHAR(64) NOT NULL,
    occurred_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE content_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    session_id VARCHAR(64),
    interaction_type VARCHAR(40) NOT NULL,
    source_page VARCHAR(60) DEFAULT '',
    mood VARCHAR(50) DEFAULT '',
    interests VARCHAR(255) DEFAULT '',
    category VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    provider VARCHAR(120) DEFAULT '',
    domain VARCHAR(120) DEFAULT '',
    content_url VARCHAR(500) NOT NULL,
    score FLOAT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
