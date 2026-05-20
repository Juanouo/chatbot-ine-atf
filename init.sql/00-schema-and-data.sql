-- Create application schemas
CREATE SCHEMA IF NOT EXISTS data;   -- domain data (indicators)
CREATE SCHEMA IF NOT EXISTS logs;   -- application telemetry

GRANT USAGE, CREATE ON SCHEMA data TO toyuser;
GRANT USAGE ON SCHEMA logs TO toyuser;

-- -- Create tables
-- CREATE TABLE users (
--     id SERIAL PRIMARY KEY,
--     username VARCHAR(50) UNIQUE NOT NULL,
--     email VARCHAR(100) UNIQUE NOT NULL,
--     first_name VARCHAR(50),
--     last_name VARCHAR(50),
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );

-- CREATE TABLE categories (
--     id SERIAL PRIMARY KEY,
--     name VARCHAR(50) NOT NULL,
--     description TEXT
-- );

-- CREATE TABLE products (
--     id SERIAL PRIMARY KEY,
--     name VARCHAR(100) NOT NULL,
--     description TEXT,
--     price DECIMAL(10,2),
--     category_id INTEGER REFERENCES categories(id),
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );

-- CREATE TABLE orders (
--     id SERIAL PRIMARY KEY,
--     user_id INTEGER REFERENCES users(id),
--     total_amount DECIMAL(10,2),
--     status VARCHAR(20) DEFAULT 'pending',
--     order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );

-- CREATE TABLE order_items (
--     id SERIAL PRIMARY KEY,
--     order_id INTEGER REFERENCES orders(id),
--     product_id INTEGER REFERENCES products(id),
--     quantity INTEGER NOT NULL,
--     unit_price DECIMAL(10,2)
-- );

-- -- Insert sample data
-- INSERT INTO users (username, email, first_name, last_name) VALUES
--     ('alice_smith', 'alice@example.com', 'Alice', 'Smith'),
--     ('bob_jones', 'bob@example.com', 'Bob', 'Jones'),
--     ('charlie_brown', 'charlie@example.com', 'Charlie', 'Brown'),
--     ('diana_prince', 'diana@example.com', 'Diana', 'Prince'),
--     ('eddie_murphy', 'eddie@example.com', 'Eddie', 'Murphy');

-- INSERT INTO categories (name, description) VALUES
--     ('Electronics', 'Electronic devices and gadgets'),
--     ('Books', 'Physical and digital books'),
--     ('Clothing', 'Apparel and accessories'),
--     ('Home & Garden', 'Home improvement and gardening supplies'),
--     ('Sports', 'Sports equipment and gear');

-- INSERT INTO products (name, description, price, category_id) VALUES
--     ('Wireless Headphones', 'Bluetooth wireless headphones with noise cancellation', 99.99, 1),
--     ('Smartphone', 'Latest model smartphone with advanced camera', 699.99, 1),
--     ('Programming Book', 'Complete guide to modern programming practices', 49.99, 2),
--     ('Fiction Novel', 'Bestselling mystery novel', 14.99, 2),
--     ('T-Shirt', 'Comfortable cotton t-shirt', 19.99, 3),
--     ('Jeans', 'Classic blue denim jeans', 59.99, 3),
--     ('Plant Pot', 'Decorative ceramic plant pot', 24.99, 4),
--     ('Garden Tools Set', 'Complete set of essential garden tools', 89.99, 4),
--     ('Tennis Racket', 'Professional grade tennis racket', 149.99, 5),
--     ('Basketball', 'Official size basketball', 29.99, 5);

-- INSERT INTO orders (user_id, total_amount, status) VALUES
--     (1, 149.98, 'completed'),
--     (2, 699.99, 'shipped'),
--     (3, 64.98, 'completed'),
--     (1, 179.97, 'pending'),
--     (4, 89.99, 'processing');

-- INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
--     (1, 1, 1, 99.99),  -- Alice bought headphones
--     (1, 5, 2, 19.99),  -- Alice bought 2 t-shirts (order total: 139.97, but let's say there was tax)
--     (2, 2, 1, 699.99), -- Bob bought smartphone
--     (3, 3, 1, 49.99),  -- Charlie bought programming book
--     (3, 4, 1, 14.99),  -- Charlie bought fiction novel
--     (4, 6, 1, 59.99),  -- Alice bought jeans
--     (4, 9, 1, 149.99), -- Alice bought tennis racket (but order total shows 179.97 with tax/shipping)
--     (5, 8, 1, 89.99);  -- Diana bought garden tools

-- -- Some useful queries to explore the data
-- -- Get all users and their order counts
-- SELECT u.username, u.email, COUNT(o.id) as order_count
-- FROM users u
-- LEFT JOIN orders o ON u.id = o.user_id
-- GROUP BY u.id, u.username, u.email
-- ORDER BY order_count DESC;

-- -- Get products by category with prices
-- SELECT c.name as category, p.name as product, p.price
-- FROM categories c
-- JOIN products p ON c.id = p.category_id
-- ORDER BY c.name, p.price DESC;

-- -- Get order details with customer info
-- SELECT 
--     o.id as order_id,
--     u.username,
--     o.order_date,
--     o.status,
--     o.total_amount,
--     COUNT(oi.id) as items_count
-- FROM orders o
-- JOIN users u ON o.user_id = u.id
-- LEFT JOIN order_items oi ON o.id = oi.order_id
-- GROUP BY o.id, u.username, o.order_date, o.status, o.total_amount
-- ORDER BY o.order_date DESC;
