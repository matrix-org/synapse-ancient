CREATE TABLE IF NOT EXISTS rooms(
    room_id TEXT PRIMARY KEY NOT NULL,
    is_public INTEGER,
    creator TEXT
);

CREATE TABLE IF NOT EXISTS room_memberships(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL, -- no foreign key to users table, it could be an id belonging to another home server
    room_id TEXT NOT NULL,
    membership TEXT NOT NULL,
    content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT, 
    room_id TEXT,
    msg_id TEXT,
    content TEXT
);

CREATE TABLE IF NOT EXISTS feedback(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT,
    feedback_type TEXT,
    fb_sender_id TEXT,
    msg_id TEXT,
    room_id TEXT,
    msg_sender_id TEXT
);

CREATE TABLE IF NOT EXISTS room_data(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT NOT NULL,
    path TEXT NOT NULL,
    content TEXT
);
