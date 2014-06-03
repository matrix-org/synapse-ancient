CREATE TABLE IF NOT EXISTS pdus(
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- twistar requires this
    pdu_id TEXT, 
    context TEXT, 
    pdu_type TEXT, 
    origin TEXT, 
    ts INTEGER, 
    is_metadata INTEGER,
    metadata_key TEXT,
    content_json TEXT,
    CONSTRAINT pdu_id_origin UNIQUE (pdu_id, origin)
);

create TABLE IF NOT EXISTS pdu_destinations(
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- twistar requires this
    pdu_row_id TEXT,
    destination TEXT,
    CONSTRAINT pdu_row_id FOREIGN KEY (pdu_row_id) REFERENCES pdus(id)
);

CREATE INDEX IF NOT EXISTS dests ON pdu_destinations (destination);

CREATE TABLE IF NOT EXISTS metadata_pdu(
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- twistar requires this
    pdu_row_id TEXT, 
    context TEXT, 
    pdu_type TEXT, 
    metatdata_key TEXT ,
    CONSTRAINT pdu_row_id UNIQUE (pdu_row_id),
    CONSTRAINT uniqueness UNIQUE (context, pdu_type, metadata_key) ON CONFLICT REPLACE
);

