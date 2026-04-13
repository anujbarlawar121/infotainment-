INSERT INTO users (name, email, password_hash, interests, preferred_mood, is_admin, created_at)
VALUES
('Admin User', 'admin@example.com', 'pbkdf2:sha256:1000000$demo$hashplaceholder', 'technology, movies, music, comedy', 'excited', 1, CURRENT_TIMESTAMP),
('Demo User', 'demo@example.com', 'pbkdf2:sha256:1000000$demo$hashplaceholder', 'world news, anime, pop music, football', 'relaxed', 0, CURRENT_TIMESTAMP);

INSERT INTO visitor_logs (user_id, name, email, login_time, browser, device, ip_address, category_viewed)
VALUES
(1, 'Admin User', 'admin@example.com', CURRENT_TIMESTAMP, 'Edge 124', 'Laptop', '127.0.0.1', 'News'),
(2, 'Demo User', 'demo@example.com', CURRENT_TIMESTAMP, 'Chrome 123', 'Desktop', '127.0.0.1', 'Music');

INSERT INTO contact_messages (name, email, subject, message, created_at)
VALUES
('Ava Martinez', 'ava@example.com', 'Feature request', 'Please add more filters for music and movie recommendations.', CURRENT_TIMESTAMP),
('Liam Chen', 'liam@example.com', 'Great dashboard', 'The analytics section is very useful. Exporting reports would be great too.', CURRENT_TIMESTAMP);

INSERT INTO recommendation_history (user_id, mood, interests, recommended_titles, viewed_at)
VALUES
(2, 'relaxed', 'world news, anime, pop music', 'Future of AI Summit, Midnight City Playlist, Aurora Nights', CURRENT_TIMESTAMP),
(1, 'excited', 'technology, comedy', 'Startup Wave, Laugh Stream, Velocity Trailer Review', CURRENT_TIMESTAMP);

INSERT INTO search_history (user_id, query, category, searched_at)
VALUES
(2, 'AI startups', 'news', CURRENT_TIMESTAMP),
(2, 'feel good songs', 'songs', CURRENT_TIMESTAMP),
(1, 'trending sci-fi films', 'movies', CURRENT_TIMESTAMP);

INSERT INTO user_preferences (user_id, favorite_category, favorite_artist, favorite_topic, updated_at)
VALUES
(2, 'Music', 'Coldplay', 'AI', CURRENT_TIMESTAMP),
(1, 'Movies', 'Hans Zimmer', 'Startups', CURRENT_TIMESTAMP);
