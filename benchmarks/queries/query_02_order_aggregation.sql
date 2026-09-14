SELECT status, COUNT(*) AS order_count, SUM(total_amount) AS revenue
FROM orders
GROUP BY status
ORDER BY revenue DESC;