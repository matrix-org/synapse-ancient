CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    password_hash TEXT,
    creation_ts INTEGER,
    UNIQUE(name) ON CONFLICT ROLLBACK
);

CREATE TABLE IF NOT EXISTS access_tokens(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    device_id TEXT,
    token TEXT NOT NULL,
    last_used INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id),
    UNIQUE(token) ON CONFLICT ROLLBACK
);
