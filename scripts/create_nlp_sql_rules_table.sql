-- ============================================================================
-- SQL Script: Create and Seed dbo.NLP_SQL_Rules
-- Purpose: Dynamic Prompt Rules & Variables Store for NLP SQL Data Generator
-- ============================================================================

-- 1. Create dbo.NLP_SQL_Rules table if it does not exist
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'NLP_SQL_Rules' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.NLP_SQL_Rules (
        RuleId INT IDENTITY(1,1) PRIMARY KEY,
        Category VARCHAR(50) NOT NULL,       -- e.g. TableMapping, FieldMapping, RoleRule, ProcedureMapping
        RuleName VARCHAR(100) NOT NULL,      -- e.g. Subject_Table_Mapping, Student_Details_SP
        RuleContent NVARCHAR(MAX) NOT NULL,  -- The prompt rule instruction text
        RoleId INT NULL,                     -- NULL = Global, 1 = Admin, 2 = Student, 3 = Instructor
        IsActive BIT DEFAULT 1 NOT NULL,     -- 1 = Active, 0 = Disabled
        DisplayOrder INT DEFAULT 0,
        CreatedDate DATETIME DEFAULT GETDATE(),
        UpdatedDate DATETIME DEFAULT GETDATE()
    );
END
GO

-- 2. Seed default dynamic rules if table is empty
IF NOT EXISTS (SELECT 1 FROM dbo.NLP_SQL_Rules)
BEGIN
    INSERT INTO dbo.NLP_SQL_Rules (Category, RuleName, RuleContent, RoleId, IsActive, DisplayOrder)
    VALUES 
    ('TableMapping', 'Subject_Table_Mapping', 'Subject table in database is dbo.Class. When subject is requested, query dbo.Class.', NULL, 1, 1),
    ('TableMapping', 'Class_Table_Mapping', 'Class table in database is dbo.SIS_Program. When class or program is requested, query dbo.SIS_Program.', NULL, 1, 2),
    ('TableMapping', 'Class_Students_Mapping', 'Class Students table is dbo.SIS_Student_Program. When class students or class enrollments are requested, query dbo.SIS_Student_Program.', NULL, 1, 3),
    ('TableMapping', 'Student_Fees_Mapping', 'When student fees, payments, or financial details are requested, query dbo.SIS_Accounting_Financials_T and join with dbo.UserInfo (or dbo.Student) on dbo.SIS_Accounting_Financials_T.ApplyAmountToId = dbo.UserInfo.UserId to retrieve student names alongside fee details.', NULL, 1, 4),
    ('FieldMapping', 'Gender_Query_Rule', 'For gender queries, select u.FirstName, u.LastName, s.StudentGenderCodeId AS Gender from dbo.UserInfo AS u JOIN dbo.Student AS s ON u.UserId = s.UserId. Do not query or subquery dbo.Code or dbo.List.', NULL, 1, 5),
    ('FieldMapping', 'Attendance_Status_Format', 'For attendance status columns (e.g. SIS_Attendance.Status), use a CASE statement to display ''Present'' or ''Absent'' instead of raw true/false or 1/0: CASE WHEN Attendance.Status = 1 OR Attendance.Status = ''true'' THEN ''Present'' ELSE ''Absent'' END AS Status.', NULL, 1, 6),
    ('ProcedureMapping', 'Student_Details_SP', 'When full or individual student profile/details/homeworks are requested for a specific student, call stored procedure dbo.SIS_Students_GetStudentDetailsByUserId: DECLARE @UserId INT = (SELECT TOP 1 UserId FROM dbo.UserInfo WHERE FirstName = ''<first>'' AND LastName = ''<last>''); EXEC dbo.SIS_Students_GetStudentDetailsByUserId @UserId = @UserId, @StudentStatusID = NULL, @GenderListId = NULL, @TeacherRoleId = NULL, @NameTitle = NULL, @AddressTypeListId = NULL, @StudentProgramStatusListID = NULL, @StudentCredentialAwarded = NULL, @StudentCredentialStatus = NULL, @StudentStatusListId = NULL, @PaymentMethods = NULL, @StudentApplyAmountTo = NULL, @CustomFieldsStudent = NULL, @LicensureExamNameListId = NULL, @LicensureExamStatusListId = NULL, @StudentJobPlacementWagesListId = NULL, @StudentJobPlacementEmploymentHoursListId = NULL.', NULL, 1, 7),
    ('RoleRule', 'Student_Role_Isolation', 'ABSOLUTE SECURITY OVERRIDE FOR STUDENT ROLE (ROLEID = 2): Active User Context: STUDENT (RoleId = 2). Active User is a Student. YOU MUST OVERRIDE AND IGNORE ANY OTHER STUDENT NUMBER OR NAME. YOU MUST ONLY QUERY AND RETURN DATA STRICTLY BELONGING TO UserId = {active_uid}.', 2, 1, 10),
    ('RoleRule', 'Instructor_Role_Isolation', 'ABSOLUTE SECURITY OVERRIDE FOR INSTRUCTOR ROLE (ROLEID = 3): Active User Context: INSTRUCTOR (RoleId = 3). YOU MUST OVERRIDE AND IGNORE ANY OTHER INSTRUCTOR NAME OR ID. YOU MUST ONLY QUERY AND RETURN DATA AND PAY DETAILS STRICTLY BELONGING TO UserId = {active_uid}.', 3, 1, 11);
END
GO
