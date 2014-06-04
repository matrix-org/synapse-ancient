-- Stores pdus and their content
CREATE TABLE IF NOT EXISTS pdus(
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- twistar requires this
    pdu_id TEXT, 
    version TEXT,
    context TEXT, 
    pdu_type TEXT, 
    origin TEXT, 
    ts INTEGER, 
    is_state INTEGER,
    state_key TEXT,
    content_json TEXT,
    unrecognized_keys TEXT,
    CONSTRAINT pdu_id_origin UNIQUE (pdu_id, origin)
);

-- Stores what the current state pdu is for a given (context, pdu_type, key) tuple
CREATE TABLE IF NOT EXISTS state_pdu(
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- twistar requires this
    pdu_row_id TEXT,
    context TEXT,
    pdu_type TEXT,
    state_key TEXT ,
    CONSTRAINT pdu_row_id UNIQUE (pdu_row_id),
    CONSTRAINT uniqueness UNIQUE (context, pdu_type, metadata_key) ON CONFLICT REPLACE
);

-- Stores where each pdu we want to send should be sent and the delivery status.
create TABLE IF NOT EXISTS pdu_destinations(
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- twistar requires this
    pdu_row_id TEXT,
    destination TEXT,
    delivered_ts INTEGER, -- or 0 if not delivered
    CONSTRAINT pdu_row_id FOREIGN KEY (pdu_row_id) REFERENCES pdus(id)
);


create INDEX IF NOT EXISTS pdu_row ON pdus(id);
CREATE INDEX IF NOT EXISTS pdu_id ON pdus(pdu_id, origin);

CREATE INDEX IF NOT EXISTS dests ON pdu_destinations (destination);

CREATE INDEX IF NOT EXISTS m_pdu_id ON metadata_pdu(pdu_id, origin);
