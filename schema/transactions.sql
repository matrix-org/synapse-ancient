CREATE TABLE IF NOT EXISTS transactions(
    transaction_id, 
    destination TEXT,
    origin TEXT, 
    data TEXT, 
    ts INTEGER,
    response_code INTEGER, 
    response TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS transactions_txid ON transactions(txid, origin);

