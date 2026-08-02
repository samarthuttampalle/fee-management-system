-- =============================================================================
-- Fix seed due dates so PartiallyPaid / unpaid-not-yet-due examples remain valid
-- relative to ~2026-08 (document "today"). Safe to re-run on existing Azure SQL.
-- =============================================================================

UPDATE dbo.Students SET DueDate = '2026-10-15' WHERE StudentID = 2;  -- Priya Patel
UPDATE dbo.Students SET DueDate = '2026-11-05' WHERE StudentID = 7;  -- Karan Kapoor
UPDATE dbo.Students SET DueDate = '2026-12-15' WHERE StudentID = 12; -- Divya Krishnan
UPDATE dbo.Students SET DueDate = '2026-12-01' WHERE StudentID = 16; -- Nisha Agarwal
UPDATE dbo.Students SET DueDate = '2026-10-20' WHERE StudentID = 19; -- Farhan Ali
GO

PRINT 'Seed due dates corrected for not-yet-due examples.';
GO
