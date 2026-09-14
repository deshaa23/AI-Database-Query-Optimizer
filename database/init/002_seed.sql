INSERT INTO users (id, name, email, created_at)
SELECT
    series,
    'User ' || series,
    'user' || series || '@example.com',
    TIMESTAMP '2022-01-01 00:00:00' + (series % 1461) * INTERVAL '1 day'
FROM generate_series(1, 50000) AS series
WHERE NOT EXISTS (SELECT 1 FROM users WHERE users.id = series);

INSERT INTO products (id, name, category, price, created_at)
SELECT
    series,
    'Product ' || series,
    (ARRAY['Books', 'Electronics', 'Home', 'Outdoor', 'Stationery'])[1 + (series % 5)],
    (5 + ((series * 37) % 99500) / 100.0)::NUMERIC(10, 2),
    TIMESTAMP '2021-01-01 00:00:00' + (series % 1826) * INTERVAL '1 day'
FROM generate_series(1, 10000) AS series
WHERE NOT EXISTS (SELECT 1 FROM products WHERE products.id = series);

INSERT INTO orders (id, user_id, product_id, quantity, total_amount, status, created_at)
SELECT
    series,
    1 + ((series * 17) % 50000),
    1 + ((series * 29) % 10000),
    1 + (series % 5),
    ((5 + (((series * 29) % 99500) / 100.0)) * (1 + (series % 5)))::NUMERIC(12, 2),
    (ARRAY['pending', 'paid', 'shipped', 'cancelled'])[1 + (series % 4)],
    TIMESTAMP '2023-01-01 00:00:00' + (series % 1096) * INTERVAL '1 minute'
FROM generate_series(1, 500000) AS series
WHERE NOT EXISTS (SELECT 1 FROM orders WHERE orders.id = series);

SELECT setval(pg_get_serial_sequence('users', 'id'), GREATEST((SELECT MAX(id) FROM users), 1));
SELECT setval(pg_get_serial_sequence('products', 'id'), GREATEST((SELECT MAX(id) FROM products), 1));
SELECT setval(pg_get_serial_sequence('orders', 'id'), GREATEST((SELECT MAX(id) FROM orders), 1));