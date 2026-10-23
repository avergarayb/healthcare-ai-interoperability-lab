CREATE TABLE hl7_inbound_message (
    message_control_id TEXT PRIMARY KEY,
    message_type TEXT NOT NULL,
    ack_code TEXT NOT NULL,
    ack_detail TEXT NOT NULL,
    placer_order_id TEXT,
    filler_order_id TEXT,
    received_at TIMESTAMPTZ NOT NULL
);
