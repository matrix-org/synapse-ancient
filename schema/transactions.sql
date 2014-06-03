CREATE TABLE IF NOT EXISTS transactions(
    transaction_id, 
    destination TEXT,
    origin TEXT, 
    data TEXT, 
    response_code INTEGER, 
    response TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS transactions_txid ON transactions(txid, origin);


CREATE TABLE IF NOT EXISTS pending_pdus(
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- twistar requires this
    pdu_json TEXT,
    ts TEXT,
    ordering INTEGER,
    destination TEXT
);

CREATE INDEX IF NOT EXISTS pending_destinations ON pending_pdus(destination);
