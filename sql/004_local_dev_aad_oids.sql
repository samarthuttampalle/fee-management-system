-- Optional local-dev helper: link seed student #4 to the local student bypass OID.
-- Run against Azure SQL after 001–003 when testing Student self-access with:
--   Authorization: Bearer local-student-token
-- OID must match LOCAL_AUTH_BYPASS_STUDENT_OID in local.settings.json.

UPDATE dbo.Students
SET AadObjectId = '11111111-1111-1111-1111-111111111111'
WHERE StudentID = 4;
GO

PRINT 'Linked StudentID=4 to local student bypass OID.';
GO
