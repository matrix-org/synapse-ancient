CREATE TABLE IF NOT EXISTS profiles(
    user_id INTEGER NOT NULL,
    displayname TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- TODO(paul): For unit testing just insert some static data
INSERT OR IGNORE INTO profiles(user_id, displayname) VALUES (123, "Frank");
