-- =========================================================================
-- Sample Table: departments
-- =========================================================================

CREATE TABLE IF NOT EXISTS departments (
    department_id INTEGER PRIMARY KEY,
    department_name TEXT NOT NULL,
    location TEXT NOT NULL,
    budget NUMERIC NOT NULL
);

INSERT INTO departments (department_id, department_name, location, budget) VALUES
(1, 'Engineering', 'Building A, Floor 3', 850000.00),
(2, 'Product & Design', 'Building A, Floor 2', 420000.00),
(3, 'Marketing', 'Building B, Floor 1', 310000.00),
(4, 'Finance & Legal', 'Building B, Floor 4', 260000.00);
