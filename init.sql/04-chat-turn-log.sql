CREATE TABLE IF NOT EXISTS chat_turn_log (
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
    UNIQUE (chat_id, message_id)
);

CREATE INDEX IF NOT EXISTS chat_turn_log_ts_idx ON chat_turn_log (ts DESC);
CREATE INDEX IF NOT EXISTS chat_turn_log_user_idx ON chat_turn_log (user_id);

GRANT INSERT, SELECT ON chat_turn_log TO toyuser;
GRANT USAGE, SELECT ON SEQUENCE chat_turn_log_id_seq TO toyuser;
GRANT SELECT ON chat_turn_log TO readonly_user;
