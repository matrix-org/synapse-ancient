CREATE TABLE IF NOT EXISTS rooms(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT NOT NULL,
    is_public INTEGER,
    topic TEXT
);

CREATE TABLE IF NOT EXISTS room_memberships(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id TEXT NOT NULL, -- no foreign key to users table, it could be an id belonging to another home server
    room_id TEXT NOT NULL,
    content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id TEXT, 
    room_id TEXT,
    msg_id TEXT,
    content TEXT
);

CREATE TABLE IF NOT EXISTS feedback(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,
    sender_synid TEXT,
    msg_id INTEGER -- no foreign key, we may receive feedback before messages
);
