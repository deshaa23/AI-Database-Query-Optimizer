SELECT id, product_id, quantity, total_amount, status, created_at
FROM orders
WHERE user_id = 4242
ORDER BY created_at DESC;