-- =============================================================================
-- Link Entra guest/member OIDs to seed rows for Azure dev smoke tests.
-- Emails updated so SendGrid reminders reach the real mailboxes.
-- =============================================================================

-- Administrator: uttampallesamarth3@gmail.com
UPDATE dbo.Administrators
SET AadObjectId = 'faf4d584-4a0f-423d-8df8-de163e2a1acb'
WHERE AdminID = 1;

-- Student: suttampalle@gmail.com  (seed #4 Ananya Iyer — Overdue)
UPDATE dbo.Students
SET
    AadObjectId = 'b31b384c-a3b0-4803-a21e-70aad2a10872',
    Email = 'suttampalle@gmail.com'
WHERE StudentID = 4;

-- Student: sammycloud2004@gmail.com  (seed #5 Vikram Singh — Overdue)
UPDATE dbo.Students
SET
    AadObjectId = 'fa054ebb-7713-4eda-80e3-b09ea9696f6d',
    Email = 'sammycloud2004@gmail.com'
WHERE StudentID = 5;
GO

SELECT AdminID, Name, AadObjectId FROM dbo.Administrators WHERE AdminID = 1;
SELECT StudentID, Name, Email, AadObjectId FROM dbo.Students WHERE StudentID IN (4, 5);
GO
