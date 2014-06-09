-- Stores what transaction ids we have received and what our response was
CREATE TABLE IF NOT EXISTS transactions(
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- twistar requires this
    transaction_id INTEGER, 
    origin TEXT, 
    ts INTEGER,
    response_code INTEGER, 
    response TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS transactions_txid ON transactions(transaction_id, origin);


-- Stores the last transaction_id we sent to a given destination
CREATE TABLE IF NOT EXISTS last_sent_transaction(
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- twistar requires this
    transaction_id INTEGER,
    destination TEXT,
    ts INTEGER
);

CREATE INDEX IF NOT EXISTS last_sent_transaction_dest ON last_sent_transaction(destination);


CREATE TABLE IF NOT EXISTS transaction_id_to_pdu(
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- twistar requires this
    transaction_id INTEGER,
    destination TEXT,
    pdu_id TEXT
);

CREATE INDEX IF NOT EXISTS transaction_id_to_pdu_dest ON transaction_id_to_pdu(destination);
CREATE INDEX IF NOT EXISTS transaction_id_to_pdu_index ON transaction_id_to_pdu(transaction_id);

