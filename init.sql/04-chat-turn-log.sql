CREATE TABLE IF NOT EXISTS logs.chat_turn_log (
    id                BIGSERIAL PRIMARY KEY,
    ts                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    chat_id           TEXT,
    message_id        TEXT,
    user_id           TEXT,
    user_name         TEXT,
    model             TEXT,
    user_message      TEXT,
    assistant_message TEXT,
    tool_uses         JSONB NOT NULL DEFAULT '{}'::jsonb,
    token_use         JSONB NOT NULL DEFAULT '{}'::jsonb,
    cost              NUMERIC(14, 8) NOT NULL DEFAULT 0,
    UNIQUE (chat_id, message_id)
);

CREATE INDEX IF NOT EXISTS chat_turn_log_ts_idx ON logs.chat_turn_log (ts DESC);
CREATE INDEX IF NOT EXISTS chat_turn_log_user_idx ON logs.chat_turn_log (user_id);

GRANT INSERT, SELECT ON logs.chat_turn_log TO toyuser;
GRANT USAGE, SELECT ON SEQUENCE logs.chat_turn_log_id_seq TO toyuser;
