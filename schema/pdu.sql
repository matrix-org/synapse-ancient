CREATE TABLE IF NOT EXISTS pdus(
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- twistar requires this
    pdu_id TEXT, 
    context TEXT, 
    pdy_type TEXT, 
    origin TEXT, 
    ts INTEGER, 
    content TEXT,
    CONSTRAINT pdu_id_origin UNIQUE (pdu_id, origin)
);

CREATE TABLE IF NOT EXISTS metadata_pdu(
    INTEGER PRIMARY KEY AUTOINCREMENT, -- twistar requires this
    pdu_row_id TEXT, 
    context TEXT, 
    pdu_type TEXT, 
    key TEXT ,
    CONSTRAINT pdu_row_id FOREIGN KEY(pdu_row_id) REFERENCES pdus(id),
    CONSTRAINT uniqueness UNIQUE (context, type, key) ON CONFLICT REPLACE
);

