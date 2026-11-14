-- SQLite; UTC ISO timestamps normalized by the loader. All cutoffs are exclusive.
-- Execute the whole script: these CHECK constraints fail closed even in SQL-only use.
-- The configuration table must contain exactly one row (id=1).
DROP TABLE IF EXISTS temp.analysis_gate;
CREATE TEMP TABLE analysis_gate (
    check_name TEXT,
    violations INTEGER CHECK (violations = 0)
);
INSERT INTO analysis_gate VALUES
    ('single configuration row', ABS((SELECT COUNT(*) FROM experiment_config)-1));
INSERT INTO analysis_gate
SELECT 'assignment conflicts', COUNT(*) FROM (
    SELECT user_id FROM assignments GROUP BY user_id
    HAVING COUNT(DISTINCT variant)>1 OR COUNT(DISTINCT assigned_at)>1
);
INSERT INTO analysis_gate
SELECT 'missing user records', COUNT(*) FROM assignments a
LEFT JOIN users u ON a.user_id=u.user_id WHERE u.user_id IS NULL;
INSERT INTO analysis_gate
SELECT 'immature observation windows', COUNT(*) FROM assignments a
CROSS JOIN experiment_config c
WHERE strftime('%Y-%m-%dT%H:%M:%S',a.assigned_at,
               '+' || (c.purchase_days+c.refund_days) || ' days') > c.extract_at;

DROP TABLE IF EXISTS user_analysis;
CREATE TABLE user_analysis AS
WITH canonical_assignments AS (
    -- The quality gate above rejects conflicts; DISTINCT removes only exact retries.
    SELECT DISTINCT user_id, variant, assigned_at FROM assignments
), eligible_orders AS (
    SELECT a.user_id, o.order_id, o.amount_cents, o.ordered_at
    FROM canonical_assignments a
    JOIN orders o ON o.user_id=a.user_id
    CROSS JOIN experiment_config c
    WHERE o.status='paid'
      AND o.ordered_at >= a.assigned_at
      AND o.ordered_at < strftime('%Y-%m-%dT%H:%M:%S',a.assigned_at,
                                  '+' || c.purchase_days || ' days')
      AND o.ordered_at < c.extract_at
), refund_per_order AS (
    -- First reduce ledger entries to an order, preventing revenue fan-out.
    SELECT o.order_id, SUM(r.amount_cents) AS refund_cents
    FROM eligible_orders o JOIN refunds r ON r.order_id=o.order_id
    CROSS JOIN experiment_config c
    WHERE r.refunded_at >= o.ordered_at
      AND r.refunded_at < strftime('%Y-%m-%dT%H:%M:%S',o.ordered_at,
                                   '+' || c.refund_days || ' days')
      AND r.refunded_at < c.extract_at
    GROUP BY o.order_id
), order_per_user AS (
    SELECT o.user_id, COUNT(*) AS order_count,
           SUM(o.amount_cents) AS gross_cents,
           SUM(COALESCE(r.refund_cents,0)) AS refund_cents,
           MAX(CASE WHEN r.refund_cents>0 THEN 1 ELSE 0 END) AS any_refund
    FROM eligible_orders o LEFT JOIN refund_per_order r ON r.order_id=o.order_id
    GROUP BY o.user_id
), event_per_user AS (
    SELECT a.user_id,
           MAX(CASE WHEN e.event_type='checkout_started' THEN 1 ELSE 0 END) AS started_checkout
    FROM canonical_assignments a CROSS JOIN experiment_config c
    LEFT JOIN checkout_events e ON a.user_id=e.user_id
      AND e.event_at >= a.assigned_at
      AND e.event_at < strftime('%Y-%m-%dT%H:%M:%S',a.assigned_at,
                                '+' || c.purchase_days || ' days')
      AND e.event_at < c.extract_at
    GROUP BY a.user_id
)
SELECT a.user_id,a.variant,a.assigned_at,u.device,u.customer_type,
       COALESCE(e.started_checkout,0) AS started_checkout,
       CASE WHEN o.order_count>0 THEN 1 ELSE 0 END AS converted,
       COALESCE(o.order_count,0) AS order_count,
       COALESCE(o.gross_cents,0) AS gross_cents,
       COALESCE(o.refund_cents,0) AS refund_cents,
       COALESCE(o.gross_cents,0)-COALESCE(o.refund_cents,0) AS net_cents,
       COALESCE(o.any_refund,0) AS any_refund
FROM canonical_assignments a LEFT JOIN users u ON u.user_id=a.user_id
LEFT JOIN order_per_user o ON o.user_id=a.user_id
LEFT JOIN event_per_user e ON e.user_id=a.user_id;
CREATE UNIQUE INDEX analysis_user ON user_analysis(user_id);
