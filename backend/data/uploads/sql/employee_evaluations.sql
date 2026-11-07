-- =========================================================================
-- Sample Table: employee_evaluations
-- (Use this to test the [+ Add Table] button on an existing database)
-- =========================================================================

CREATE TABLE IF NOT EXISTS employee_evaluations (
    eval_id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL,
    review_period TEXT NOT NULL,
    performance_score NUMERIC NOT NULL,
    reviewer_notes TEXT NOT NULL,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

INSERT INTO employee_evaluations (eval_id, employee_id, review_period, performance_score, reviewer_notes) VALUES
(1, 101, '2024-Annual', 4.9, 'Exceptional architectural leadership and zero downtime migrations.'),
(2, 102, '2024-Annual', 4.8, 'Pioneered self-correcting text-to-SQL guardrails ahead of schedule.'),
(3, 103, '2024-Annual', 4.7, 'Outstanding roadmap execution across cross-functional teams.'),
(4, 104, '2024-Annual', 4.6, 'Delivered high-converting modern dark mode UI components.'),
(5, 105, '2024-Annual', 4.5, 'Generated 38% organic user growth through targeted tech campaigns.');
