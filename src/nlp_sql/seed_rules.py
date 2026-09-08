from __future__ import annotations

import logging
from dotenv import load_dotenv
from sqlalchemy import text

from nlp_sql.config import load_config
from nlp_sql.rules_store import RulesStore

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INITIAL_RULES = [
    {
        "category": "TableMapping",
        "name": "Subject_Table_Mapping",
        "content": "Subject table in database is dbo.Class. When subject is requested, query dbo.Class.",
        "role_id": None,
        "display_order": 1,
    },
    {
        "category": "TableMapping",
        "name": "Class_Table_Mapping",
        "content": "Class table in database is dbo.SIS_Program. When class or program is requested, query dbo.SIS_Program.",
        "role_id": None,
        "display_order": 2,
    },
    {
        "category": "TableMapping",
        "name": "Class_Students_Mapping",
        "content": "Class Students table is dbo.SIS_Student_Program. When class students or class enrollments are requested, query dbo.SIS_Student_Program.",
        "role_id": None,
        "display_order": 3,
    },
    {
        "category": "TableMapping",
        "name": "Student_Fees_Mapping",
        "content": "When student fees, payments, or financial details are requested, query dbo.SIS_Accounting_Financials_T and join with dbo.UserInfo (or dbo.Student) on dbo.SIS_Accounting_Financials_T.ApplyAmountToId = dbo.UserInfo.UserId to retrieve student names alongside fee details.",
        "role_id": None,
        "display_order": 4,
    },
    {
        "category": "FieldMapping",
        "name": "Gender_Query_Rule",
        "content": "For gender queries, select u.FirstName, u.LastName, s.StudentGenderCodeId AS Gender from dbo.UserInfo AS u JOIN dbo.Student AS s ON u.UserId = s.UserId. Do not query or subquery dbo.Code or dbo.List.",
        "role_id": None,
        "display_order": 5,
    },
    {
        "category": "FieldMapping",
        "name": "Attendance_Status_Format",
        "content": "For attendance status columns (e.g. SIS_Attendance.Status), use a CASE statement to display 'Present' or 'Absent' instead of raw true/false or 1/0: CASE WHEN Attendance.Status = 1 OR Attendance.Status = 'true' THEN 'Present' ELSE 'Absent' END AS Status.",
        "role_id": None,
        "display_order": 6,
    },
    {
        "category": "ProcedureMapping",
        "name": "Student_Details_SP",
        "content": "When full or individual student profile/details/homeworks are requested for a specific student, call stored procedure dbo.SIS_Students_GetStudentDetailsByUserId: DECLARE @UserId INT = (SELECT TOP 1 UserId FROM dbo.UserInfo WHERE FirstName = '<first>' AND LastName = '<last>'); EXEC dbo.SIS_Students_GetStudentDetailsByUserId @UserId = @UserId, @StudentStatusID = NULL, @GenderListId = NULL, @TeacherRoleId = NULL, @NameTitle = NULL, @AddressTypeListId = NULL, @StudentProgramStatusListID = NULL, @StudentCredentialAwarded = NULL, @StudentCredentialStatus = NULL, @StudentStatusListId = NULL, @PaymentMethods = NULL, @StudentApplyAmountTo = NULL, @CustomFieldsStudent = NULL, @LicensureExamNameListId = NULL, @LicensureExamStatusListId = NULL, @StudentJobPlacementWagesListId = NULL, @StudentJobPlacementEmploymentHoursListId = NULL.",
        "role_id": None,
        "display_order": 7,
    },
    {
        "category": "RoleRule",
        "name": "Student_Role_Isolation",
        "content": "ABSOLUTE SECURITY OVERRIDE FOR STUDENT ROLE (ROLEID = 2): Active User Context: STUDENT (RoleId = 2). Active User is a Student. YOU MUST OVERRIDE AND IGNORE ANY OTHER STUDENT NUMBER OR NAME. YOU MUST ONLY QUERY AND RETURN DATA STRICTLY BELONGING TO UserId = {active_uid}.",
        "role_id": 2,
        "display_order": 10,
    },
]

TABLE_DDL = """
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'NLP_SQL_Rules' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.NLP_SQL_Rules (
        RuleId INT IDENTITY(1,1) PRIMARY KEY,
        Category VARCHAR(50) NOT NULL,
        RuleName VARCHAR(100) NOT NULL,
        RuleContent NVARCHAR(MAX) NOT NULL,
        RoleId INT NULL,
        IsActive BIT DEFAULT 1 NOT NULL,
        DisplayOrder INT DEFAULT 0,
        CreatedDate DATETIME DEFAULT GETDATE(),
        UpdatedDate DATETIME DEFAULT GETDATE()
    );
END
"""

SQLITE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS dbo_NLP_SQL_Rules (
    RuleId INTEGER PRIMARY KEY AUTOINCREMENT,
    Category TEXT NOT NULL,
    RuleName TEXT NOT NULL,
    RuleContent TEXT NOT NULL,
    RoleId INTEGER NULL,
    IsActive INTEGER DEFAULT 1 NOT NULL,
    DisplayOrder INTEGER DEFAULT 0,
    CreatedDate TEXT DEFAULT CURRENT_TIMESTAMP,
    UpdatedDate TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def seed_database_rules() -> None:
    config = load_config()
    engine = RulesStore.get_default_engine(config)
    if engine is None:
        logger.error("No database engine available for seeding rules.")
        return

    logger.info("Initializing dbo.NLP_SQL_Rules table...")
    with engine.begin() as conn:
        dialect_name = engine.dialect.name
        if dialect_name == "mssql":
            conn.execute(text(TABLE_DDL))
        else:
            # Fallback table DDL for SQLite / Postgres
            conn.execute(text(TABLE_DDL.replace("dbo.NLP_SQL_Rules", "NLP_SQL_Rules")))

    # Check if table already has rows
    with engine.connect() as conn:
        try:
            count = conn.execute(text("SELECT COUNT(*) FROM dbo.NLP_SQL_Rules")).scalar()
        except Exception:
            count = conn.execute(text("SELECT COUNT(*) FROM NLP_SQL_Rules")).scalar()

    if count and count > 0:
        logger.info(f"dbo.NLP_SQL_Rules already contains {count} rules. Skipping initial seed.")
        return

    logger.info("Seeding initial rules into dbo.NLP_SQL_Rules...")
    for rule in INITIAL_RULES:
        RulesStore.create_rule(
            config,
            category=rule["category"],
            rule_name=rule["name"],
            rule_content=rule["content"],
            role_id=rule["role_id"],
            display_order=rule["display_order"],
        )
    logger.info("Database rules seeded successfully!")


if __name__ == "__main__":
    seed_database_rules()
