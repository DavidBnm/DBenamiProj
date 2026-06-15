-- Inefficient SQL query for testing
-- Poor practices: SELECT *, subquery instead of JOIN, no column constraints
SELECT *
FROM orders
WHERE user_id IN (
    SELECT user_id 
    FROM users 
    WHERE country = 'United States'
)
AND order_date > '2023-01-01'
ORDER BY order_date DESC;
