-- =========================================================================
-- Sample Table: projects
-- =========================================================================

CREATE TABLE IF NOT EXISTS projects (
    project_id INTEGER PRIMARY KEY,
    project_name TEXT NOT NULL,
    lead_employee_id INTEGER NOT NULL,
    budget NUMERIC NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (lead_employee_id) REFERENCES employees(employee_id)
);

INSERT INTO projects (project_id, project_name, lead_employee_id, budget, status) VALUES
(501, 'Text-to-SQL Multi-Agent Intelligence', 102, 120000.00, 'In Progress'),
(502, 'NextGen Enterprise Cloud Migration', 101, 240000.00, 'In Progress'),
(503, 'AI Driven UX Design System', 104, 75000.00, 'Completed'),
(504, 'Global Brand Expansion Q3', 105, 95000.00, 'Planning');
