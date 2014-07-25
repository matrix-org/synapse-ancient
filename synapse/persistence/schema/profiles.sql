CREATE TABLE IF NOT EXISTS profiles(
    user_id INTEGER NOT NULL,
    displayname TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
