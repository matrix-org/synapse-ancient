CREATE TABLE IF NOT EXISTS presence(
  user_id INTEGER NOT NULL,
  state INTEGER,
  status_message TEXT,
  FOREIGN KEY(user_id) REFERENCES users(id)
);
