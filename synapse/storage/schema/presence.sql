CREATE TABLE IF NOT EXISTS presence(
  user_id INTEGER NOT NULL,
  state INTEGER,
  status_msg TEXT,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

-- For each of /my/ users which possibly-remote users are allowed to see their
-- presence state
CREATE TABLE IF NOT EXISTS presence_allow_inbound(
  observed_user_id INTEGER NOT NULL,
  observer_user_id TEXT, -- a UserID,
  FOREIGN KEY(observed_user_id) REFERENCES users(id)
);

-- For each of /my/ users (watcher), which possibly-remote users are they
-- watching?
CREATE TABLE IF NOT EXISTS presence_list(
  user_id INTEGER NOT NULL,
  observed_user_id TEXT, -- a UserID,
  accepted BOOLEAN,
  FOREIGN KEY(user_id) REFERENCES users(id)
);
