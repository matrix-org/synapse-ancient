CREATE TABLE IF NOT EXISTS context_edge_pdus(
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- twistar requires this
    pdu_id TEXT, 
    origin TEXT,
    context TEXT, 
    CONSTRAINT context_edge_pdu_id_origin UNIQUE (pdu_id, origin)
);

CREATE TABLE IF NOT EXISTS origin_edge_pdus(
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- twistar requires this
    pdu_id TEXT,
    origin TEXT,
    CONSTRAINT origin_edge_pdu_id_origin UNIQUE (pdu_id, origin)
);

CREATE INDEX IF NOT EXISTS context_edge_pdu_id ON context_edge_pdus(pdu_id, origin); 
CREATE INDEX IF NOT EXISTS origin_edge_pdu_id ON origin_edge_pdus(pdu_id, origin);
