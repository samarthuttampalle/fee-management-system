-- =============================================================================
-- Fee Management System — indexes, filtered unique keys, UpdatedAt trigger
-- =============================================================================

CREATE UNIQUE INDEX UX_Students_AadObjectId
    ON dbo.Students(AadObjectId)
    WHERE AadObjectId IS NOT NULL;
GO

CREATE INDEX IX_Students_DueDate
    ON dbo.Students(DueDate)
    INCLUDE (TotalFee, PaidAmount);
GO

CREATE INDEX IX_Students_Course ON dbo.Students(Course);
GO

CREATE UNIQUE INDEX UX_Administrators_AadObjectId
    ON dbo.Administrators(AadObjectId)
    WHERE AadObjectId IS NOT NULL;
GO

CREATE INDEX IX_ReminderLog_StudentID_SentAt
    ON dbo.ReminderLog(StudentID, SentAt DESC);
GO

-- Trigger to keep UpdatedAt current on every UPDATE
CREATE OR ALTER TRIGGER trg_Students_UpdatedAt
ON dbo.Students
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE s
    SET UpdatedAt = SYSUTCDATETIME()
    FROM dbo.Students s
    INNER JOIN inserted i ON s.StudentID = i.StudentID;
END
GO

PRINT 'Indexes, constraints helpers, and UpdatedAt trigger created successfully.';
GO
