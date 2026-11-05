PRAGMA foreign_keys = ON;
CREATE TABLE users (
    user_id TEXT PRIMARY KEY NOT NULL,
    device TEXT NOT NULL CHECK (device IN ('mobile', 'desktop')),
    customer_type TEXT NOT NULL CHECK (customer_type IN ('new', 'returning'))
);
-- Raw deliveries intentionally have no unique user key: exact retries are allowed.
CREATE TABLE assignments (
    user_id TEXT NOT NULL REFERENCES users(user_id),
    variant TEXT NOT NULL CHECK (variant IN ('control', 'new')),
    assigned_at TEXT NOT NULL
);
CREATE TABLE checkout_events (
    event_id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    event_type TEXT NOT NULL CHECK (event_type IN ('checkout_started','checkout_completed')),
    event_at TEXT NOT NULL
);
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    ordered_at TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0 AND typeof(amount_cents) = 'integer'),
    status TEXT NOT NULL CHECK (status IN ('paid','cancelled'))
);
CREATE TABLE refunds (
    refund_id TEXT PRIMARY KEY NOT NULL,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    refunded_at TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0 AND typeof(amount_cents) = 'integer')
);
CREATE TABLE experiment_config (
    id INTEGER PRIMARY KEY CHECK(id=1),
    purchase_days INTEGER NOT NULL CHECK(purchase_days>0),
    refund_days INTEGER NOT NULL CHECK(refund_days>0),
    extract_at TEXT NOT NULL
);
CREATE INDEX orders_user_time ON orders(user_id, ordered_at);
CREATE INDEX refunds_order_time ON refunds(order_id, refunded_at);
CREATE INDEX events_user_time ON checkout_events(user_id, event_at);
CREATE INDEX assignments_user ON assignments(user_id);
