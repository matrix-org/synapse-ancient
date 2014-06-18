-- Stores pdus and their content
CREATE TABLE IF NOT EXISTS pdus(
    pdu_id TEXT, 
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
CREATE TABLE IF NOT EXISTS state_pdus(
    pdu_id TEXT,
    origin TEXT,
    context TEXT,
    pdu_type TEXT,
    state_key TEXT ,
    CONSTRAINT pdu_row_id UNIQUE (pdu_row_id),
    CONSTRAINT uniqueness UNIQUE (context, pdu_type, state_key) ON CONFLICT REPLACE
);

-- Stores where each pdu we want to send should be sent and the delivery status.
create TABLE IF NOT EXISTS pdu_destinations(
    pdu_id TEXT,
    origin TEXT,
    destination TEXT,
    delivered_ts INTEGER DEFAULT 0, -- or 0 if not delivered
    CONSTRAINT uniqueness UNIQUE (pdu_id, origin, destination) ON CONFLICT REPLACE
);

CREATE TABLE IF NOT EXISTS pdu_extremeties(
    pdu_id TEXT,
    origin TEXT,
    context TEXT,
    CONSTRAINT uniqueness UNIQUE (pdu_id, origin, context) ON CONFLICT REPLACE
);

CREATE TABLE IF NOT EXISTS pdu_edges(
    pdu_id TEXT,
    origin TEXT,
    prev_pdu_id TEXT,
    prev_origin TEXT,
    context TEXT,
    CONSTRAINT uniqueness UNIQUE (pdu_id, origin, prev_pdu_id, prev_origin, context)
);


create INDEX IF NOT EXISTS pdu_row ON pdus(id);
CREATE INDEX IF NOT EXISTS pdu_id ON pdus(pdu_id, origin);

CREATE INDEX IF NOT EXISTS dests_id ON pdu_destinations (pdu_id, origin);
-- CREATE INDEX IF NOT EXISTS dests ON pdu_destinations (destination);

CREATE INDEX IF NOT EXISTS state_pdu_id ON state_pdus(pdu_row_id);

CREATE INDEX IF NOT EXISTS pdu_extrem_context ON pdu_extremeties(context);
CREATE INDEX IF NOT EXISTS pdu_edges_id ON pdu_edges(pdu_id, origin);

