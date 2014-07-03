CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    creation_ts INTEGER
);

CREATE TABLE IF NOT EXISTS access_tokens(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    device_id TEXT NOT NULL,
    token TEXT NOT NULL,
    last_used INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id),
    UNIQUE(user_id, device_id) ON CONFLICT REPLACE
);
