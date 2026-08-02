-- =============================================================================
-- Fee Management System — sample data (20 students + 3 administrators)
-- Email addresses added per TDD §24.1 (required for reminder workflow).
-- Due dates calibrated relative to document "today" ≈ 2026-08-01 so that:
--   - Overdue, Paid, and PartiallyPaid (incl. unpaid-not-yet-due) are all present
-- =============================================================================

INSERT INTO dbo.Students (Name, Course, Email, TotalFee, PaidAmount, DueDate) VALUES
('Aarav Sharma',       'B.Tech Computer Science', 'aarav.sharma@institution.edu',       120000.00, 120000.00, '2026-03-15'), -- Paid
('Priya Patel',        'B.Tech Electronics',      'priya.patel@institution.edu',        110000.00,  55000.00, '2026-10-15'), -- Partially Paid, not yet due
('Rohan Mehta',        'MBA Finance',             'rohan.mehta@institution.edu',        250000.00, 250000.00, '2026-01-10'), -- Paid
('Ananya Iyer',        'B.Sc Physics',            'ananya.iyer@institution.edu',         80000.00,  40000.00, '2026-02-01'), -- Overdue
('Vikram Singh',       'B.Tech Mechanical',       'vikram.singh@institution.edu',       115000.00,       0.00, '2026-01-20'), -- Overdue
('Sneha Reddy',        'B.Com Honours',           'sneha.reddy@institution.edu',         70000.00,  70000.00, '2026-04-10'), -- Paid
('Karan Kapoor',       'MCA',                     'karan.kapoor@institution.edu',       130000.00,  65000.00, '2026-11-05'), -- Partially Paid, not yet due
('Ishita Verma',       'B.Tech Civil',            'ishita.verma@institution.edu',       118000.00,  30000.00, '2026-01-05'), -- Overdue
('Aditya Nair',        'BBA',                     'aditya.nair@institution.edu',         90000.00,  90000.00, '2025-12-20'), -- Paid
('Meera Joshi',        'M.Sc Data Science',       'meera.joshi@institution.edu',        140000.00,       0.00, '2026-01-25'), -- Overdue
('Arjun Rao',          'B.Tech Computer Science', 'arjun.rao@institution.edu',          120000.00, 120000.00, '2026-05-15'), -- Paid
('Divya Krishnan',     'B.A. Economics',          'divya.krishnan@institution.edu',      65000.00,  32500.00, '2026-12-15'), -- Partially Paid, not yet due
('Siddharth Malhotra', 'MBA Marketing',           'siddharth.malhotra@institution.edu', 245000.00, 200000.00, '2026-01-15'), -- Overdue (partial + past due)
('Pooja Desai',        'B.Sc Chemistry',          'pooja.desai@institution.edu',         75000.00,  75000.00, '2026-03-01'), -- Paid
('Rahul Bose',         'B.Tech Electronics',      'rahul.bose@institution.edu',         110000.00,  55000.00, '2026-01-08'), -- Overdue (partial + past due)
('Nisha Agarwal',      'B.Com Honours',           'nisha.agarwal@institution.edu',       70000.00,       0.00, '2026-12-01'), -- Not yet due, unpaid (PartiallyPaid bucket)
('Manish Kumar',       'MCA',                     'manish.kumar@institution.edu',       130000.00, 130000.00, '2026-02-20'), -- Paid
('Kavya Pillai',       'B.Tech Civil',            'kavya.pillai@institution.edu',       118000.00,  59000.00, '2026-01-12'), -- Overdue (partial + past due)
('Farhan Ali',         'BBA',                     'farhan.ali@institution.edu',          90000.00,  45000.00, '2026-10-20'), -- Partially Paid, not yet due
('Tanvi Chatterjee',   'M.Sc Data Science',       'tanvi.chatterjee@institution.edu',   140000.00,  70000.00, '2026-01-18'); -- Overdue (partial + past due)
GO

INSERT INTO dbo.Administrators (Name, Role) VALUES
('Dr. Sunita Rao', 'Administrator'),
('Mr. Ajay Verma', 'Administrator'),
('Ms. Leela Menon', 'Administrator');
GO

PRINT 'Sample data seeded successfully.';
GO
