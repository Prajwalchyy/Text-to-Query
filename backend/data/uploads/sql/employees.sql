-- =========================================================================
-- Sample Table: employees
-- =========================================================================

CREATE TABLE IF NOT EXISTS employees (
    employee_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    department_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    salary NUMERIC NOT NULL,
    hire_date DATE NOT NULL,
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

INSERT INTO employees (employee_id, first_name, last_name, department_id, role, salary, hire_date) VALUES
(101, 'Sarah', 'Connor', 1, 'Lead Systems Architect', 145000.00, '2021-03-15'),
(102, 'Alex', 'Murphy', 1, 'Senior AI Engineer', 128000.00, '2022-06-01'),
(103, 'Elena', 'Rostova', 2, 'Principal Product Manager', 118000.00, '2020-11-12'),
(104, 'Marcus', 'Vance', 2, 'Lead UI/UX Designer', 98000.00, '2023-01-20'),
(105, 'Chloe', 'Decker', 3, 'Growth Marketing Lead', 92000.00, '2022-09-10'),
(106, 'David', 'Kim', 4, 'Senior Financial Analyst', 105000.00, '2021-08-04');
