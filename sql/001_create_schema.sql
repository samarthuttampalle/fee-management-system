-- =============================================================================
-- Fee Management System — schema (Azure SQL)
-- Run against the target database (e.g. sqldb-feemgmt-dev), not master.
-- =============================================================================

PRINT CONCAT('Creating schema in database: ', DB_NAME());
GO

CREATE TABLE dbo.Students (
    StudentID     INT IDENTITY(1,1)      NOT NULL,
    Name          NVARCHAR(100)          NOT NULL,
    Course        NVARCHAR(100)          NOT NULL,
    Email         NVARCHAR(255)          NOT NULL,
    TotalFee      DECIMAL(10,2)          NOT NULL,
    PaidAmount    DECIMAL(10,2)          NOT NULL CONSTRAINT DF_Students_PaidAmount DEFAULT (0),
    DueDate       DATE                   NOT NULL,
    AadObjectId   UNIQUEIDENTIFIER       NULL,
    CreatedAt     DATETIME2(3)           NOT NULL CONSTRAINT DF_Students_CreatedAt DEFAULT (SYSUTCDATETIME()),
    UpdatedAt     DATETIME2(3)           NOT NULL CONSTRAINT DF_Students_UpdatedAt DEFAULT (SYSUTCDATETIME()),
    RowVersion    ROWVERSION,
    CONSTRAINT PK_Students PRIMARY KEY CLUSTERED (StudentID),
    CONSTRAINT CK_Students_TotalFee_NonNegative CHECK (TotalFee >= 0),
    CONSTRAINT CK_Students_PaidAmount_NonNegative CHECK (PaidAmount >= 0),
    CONSTRAINT CK_Students_PaidAmount_Bound CHECK (PaidAmount <= TotalFee * 1.5)
);
GO

CREATE TABLE dbo.Administrators (
    AdminID       INT IDENTITY(1,1)      NOT NULL,
    Name          NVARCHAR(100)          NOT NULL,
    Role          NVARCHAR(50)           NOT NULL,
    AadObjectId   UNIQUEIDENTIFIER       NULL,
    CreatedAt     DATETIME2(3)           NOT NULL CONSTRAINT DF_Administrators_CreatedAt DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_Administrators PRIMARY KEY CLUSTERED (AdminID),
    CONSTRAINT CK_Administrators_Role CHECK (Role IN ('Administrator'))
);
GO

CREATE TABLE dbo.ReminderLog (
    ReminderLogID BIGINT IDENTITY(1,1)   NOT NULL,
    StudentID     INT                    NOT NULL,
    SentAt        DATETIME2(3)           NOT NULL CONSTRAINT DF_ReminderLog_SentAt DEFAULT (SYSUTCDATETIME()),
    Status        NVARCHAR(20)           NOT NULL,
    ErrorDetail   NVARCHAR(500)          NULL,
    CONSTRAINT PK_ReminderLog PRIMARY KEY CLUSTERED (ReminderLogID),
    CONSTRAINT FK_ReminderLog_Students FOREIGN KEY (StudentID) REFERENCES dbo.Students(StudentID),
    CONSTRAINT CK_ReminderLog_Status CHECK (Status IN ('Sent', 'Failed'))
);
GO

PRINT 'Schema created successfully.';
GO
