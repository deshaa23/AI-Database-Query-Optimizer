SELECT
    products.category,
    products.name,
    COUNT(orders.id) AS order_count,
    SUM(orders.quantity) AS units_sold
FROM orders
JOIN products ON products.id = orders.product_id
GROUP BY products.category, products.name
ORDER BY order_count DESC
LIMIT 20;