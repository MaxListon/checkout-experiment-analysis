-- Read-only diagnostics and metric summary after 01_user_analysis.sql.
SELECT COUNT(*) AS raw_assignment_rows, COUNT(DISTINCT user_id) AS unique_assigned_users
FROM assignments;
SELECT user_id, COUNT(*) AS deliveries FROM assignments GROUP BY user_id HAVING COUNT(*)>1;
SELECT user_id FROM assignments GROUP BY user_id
HAVING COUNT(DISTINCT variant)>1 OR COUNT(DISTINCT assigned_at)>1;
SELECT variant, COUNT(*) AS assigned_users, SUM(converted) AS buyers,
       AVG(converted*1.0) AS conversion,
       SUM(order_count) AS orders,
       SUM(gross_cents)/100.0 AS gross_revenue,
       AVG(gross_cents)/100.0 AS gross_revenue_per_user,
       AVG(net_cents)/100.0 AS after_refund_revenue_per_user,
       AVG(any_refund*1.0) AS refunded_user_rate,
       SUM(any_refund)*1.0/NULLIF(SUM(converted),0) AS refund_rate_among_buyers,
       SUM(order_count)*1.0/NULLIF(SUM(converted),0) AS orders_per_buyer,
       SUM(gross_cents)/100.0/NULLIF(SUM(order_count),0) AS average_order_value
FROM user_analysis GROUP BY variant;
