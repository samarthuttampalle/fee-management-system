-- =============================================================================
-- Align Administrators.Role with Entra App Roles: Administrator + Student only.
-- Removes unused SuperAdmin value. Safe to re-run.
-- =============================================================================

UPDATE dbo.Administrators
SET Role = N'Administrator'
WHERE Role = N'SuperAdmin';
GO

IF EXISTS (
    SELECT 1
    FROM sys.check_constraints
    WHERE name = N'CK_Administrators_Role'
      AND parent_object_id = OBJECT_ID(N'dbo.Administrators')
)
BEGIN
    ALTER TABLE dbo.Administrators DROP CONSTRAINT CK_Administrators_Role;
END
GO

ALTER TABLE dbo.Administrators
ADD CONSTRAINT CK_Administrators_Role CHECK (Role IN ('Administrator'));
GO

PRINT 'SuperAdmin removed; Administrators.Role allows Administrator only.';
GO
