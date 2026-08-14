from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from nlp_sql.config import LLMSettings
from nlp_sql.safety import extract_sql_fenced


def _parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError("Model did not return a JSON object")
    return json.loads(m.group(0))


def _is_local_url(base_url: str) -> bool:
    try:
        p = urlparse(base_url)
        return p.hostname in ("127.0.0.1", "localhost", None) or (p.hostname or "").endswith(
            ".local"
        )
    except Exception:
        return False


def _auth_headers(base_url: str) -> dict[str, str]:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key and not _is_local_url(base_url):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. For local OpenAI-compatible servers (Ollama, etc.) "
            "set base_url to http://127.0.0.1:...; an empty key is allowed for many local servers."
        )
    h: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


def generate_sql_sync(
    user_request: str,
    schema_context: str,
    database_ids: list[str],
    settings: LLMSettings,
    role_id: int | None = 1,
    user_id: int | None = 296,
) -> tuple[str, str, str | None, dict[str, int]]:
    """Call OpenAI-compatible chat API; return (database_id, sql, explanation, usage)."""
    system_lines = [
        "You translate natural language to SQL. Follow database limits and dialect rules.",
        "  - If dialect is 'mssql': Use T-SQL (TOP N, GETDATE(), ISNULL(), string concat with +).",
        "  - If dialect is 'sqlite': Use standard SQLite syntax and functions.",
        "Output a single JSON object only, no markdown, with keys:",
        '  "database_id" (one of the allowed ids), "sql" (one read-only SELECT, WITH, DECLARE, or EXEC query), ',
        '  and optional "explanation" (short). Use only tables and columns from the schema context.',
        "Qualify table names EXACTLY as shown in the schema context. Do not prepend database IDs to table names. No SQL comments.",
        "CRITICAL FOR ALIASED COLUMNS: If a table is assigned an alias in FROM or JOIN (e.g., `FROM dbo.SIS_Student_Course_Test_Enrollment AS Enrollment`), ALL column references to that table in SELECT, WHERE, and JOIN MUST use the alias (`Enrollment.Points`), NEVER the full schema-qualified table name (`dbo.SIS_Student_Course_Test_Enrollment.Points`).",
        "CRITICAL FOR STUDENT GENDER QUERIES:",
        "  - For student gender queries, select `u.FirstName`, `u.LastName`, `s.StudentGenderCodeId AS Gender` from `dbo.UserInfo AS u` JOIN `dbo.Student AS s` ON `u.UserId = s.UserId` (or LEFT JOIN `dbo.Details AS d` ON `s.StudentId = d.StudentNo`). DO NOT construct subqueries against `dbo.Code` or `dbo.List`.",
        "CRITICAL FOR BOOLEAN / ATTENDANCE / STATUS FLAGS:",
        "  - When selecting attendance status or boolean/bit flags (e.g., `SIS_Attendance.Status`, `IsPresent`, `IsActive`, etc.), DO NOT return raw `true`/`false` or `1`/`0`.",
        "  - For attendance status, ALWAYS use a CASE statement to display human-readable values: `CASE WHEN A.Status = 1 OR A.Status = 'true' THEN 'Present' ELSE 'Absent' END AS Status`.",
        "  - For other status or boolean flags, convert raw bits/booleans to user-friendly terms (e.g. 'Active'/'Inactive') using `CASE` statements.",
        "CRITICAL FOR STUDENT GRADE POINTS & MARKS:",
        "  - When grade points, test points, max points, or marks are requested for students:",
        "  - Query `dbo.SIS_Student_Course_Test_Enrollment AS cte`.",
        "  - LEFT JOIN `dbo.SIS_Course_Grades AS cg` ON `cg.CourseGradeId = cte.TestId`.",
        "  - LEFT JOIN `dbo.Class AS cl` ON `cte.CourseId = cl.ClassId`.",
        "  - LEFT JOIN `dbo.Student AS s` ON `s.UserId = cte.UserId`.",
        "  - LEFT JOIN `dbo.UserInfo AS u` ON `u.UserId = cte.UserId` (or `s.UserId = u.UserId`).",
        "  - Filter by student number matching either `s.StudentNumber` or `s.LegacyStudentId`.",
        "  - Select `cte.Points AS TotalPoints`, `cg.MaxPoints AS TotalMaxMarks`, `cg.GradeName`, `cl.ClassDesc`, `s.StudentNumber`, `s.LegacyStudentId`, and student name (`u.FirstName + ' ' + u.LastName`).",
        "CRITICAL FOR TABLE MAPPINGS:",
        "  - Subject table: When 'Subject' or 'Subjects' is requested, query the `dbo.Class` table.",
        "  - Class table: When 'Class' or 'Classes' or 'Program' is requested, query the `dbo.SIS_Program` table.",
        "  - Class Students table: When 'Class Students' or student class enrollment is requested, query the `dbo.SIS_Student_Program` table.",
        "CRITICAL FOR STUDENT FEES & FINANCIALS:",
        "  - When student fees or financial details are requested, query the `dbo.SIS_Accounting_Financials_T` table.",
        "  - Join `dbo.SIS_Accounting_Financials_T` with `dbo.UserInfo` (or `dbo.Student`) on `dbo.SIS_Accounting_Financials_T.ApplyAmountToId = dbo.UserInfo.UserId` to link student names to their fee details.",
        "CRITICAL FOR INDIVIDUAL STUDENT DETAILS & HOMEWORKS:",
        "  - When full or individual student profile/details/homeworks are requested for a specific student (by name or UserId):",
        "  - MANDATORY: Call stored procedure `dbo.SIS_Students_GetStudentDetailsByUserId` using all 17 parameters (returns profile, contact, courses, groups, financials, and homeworks):",
        "    DECLARE @UserId INT = (SELECT TOP 1 UserId FROM dbo.UserInfo WHERE FirstName = '<FirstName>' AND LastName = '<LastName>');",
        "    EXEC dbo.SIS_Students_GetStudentDetailsByUserId @UserId = @UserId, @StudentStatusID = NULL, @GenderListId = NULL, @TeacherRoleId = NULL, @NameTitle = NULL, @AddressTypeListId = NULL, @StudentProgramStatusListID = NULL, @StudentCredentialAwarded = NULL, @StudentCredentialStatus = NULL, @StudentStatusListId = NULL, @PaymentMethods = NULL, @StudentApplyAmountTo = NULL, @CustomFieldsStudent = NULL, @LicensureExamNameListId = NULL, @LicensureExamStatusListId = NULL, @StudentJobPlacementWagesListId = NULL, @StudentJobPlacementEmploymentHoursListId = NULL;",
        "  - For attendance data, also LEFT JOIN dbo.SIS_Attendance AS A ON UI.UserId = A.UserId with CASE WHEN A.Status = 1 OR A.Status = 'true' THEN 'Present' ELSE 'Absent' END AS AttendanceStatus.",
        "  - For fee data, also LEFT JOIN dbo.SIS_Accounting_Financials_T AS F ON F.ApplyAmountToId = UI.UserId."
    ]

    # Inject Role-Based Access Control (RBAC) constraints
    active_role = role_id if role_id is not None else 1
    active_uid = user_id if user_id is not None else 296

    if active_role == 2:  # Student Role (RoleId = 2)
        system_lines.append(
            f"\nCRITICAL ROLE-BASED SECURITY CONSTRAINT (ROLE = STUDENT, ROLEID = 2):\n"
            f"  - Active User: STUDENT (RoleId = 2, UserId = {active_uid}).\n"
            f"  - MANDATORY SECURITY CONSTRAINT: The active user is a Student. You MUST strictly scope and filter ALL queries so that only data belonging to UserId = {active_uid} is retrieved.\n"
            f"  - The student MUST NEVER see, query, list, or access data, grades, attendance, fees, or profiles belonging to any other students.\n"
            f"  - For individual profile/details requests, run: EXEC dbo.SIS_Students_GetStudentDetailsByUserId @UserId = {active_uid}, @StudentStatusID = NULL, @GenderListId = NULL, @TeacherRoleId = NULL, @NameTitle = NULL, @AddressTypeListId = NULL, @StudentProgramStatusListID = NULL, @StudentCredentialAwarded = NULL, @StudentCredentialStatus = NULL, @StudentStatusListId = NULL, @PaymentMethods = NULL, @StudentApplyAmountTo = NULL, @CustomFieldsStudent = NULL, @LicensureExamNameListId = NULL, @LicensureExamStatusListId = NULL, @StudentJobPlacementWagesListId = NULL, @StudentJobPlacementEmploymentHoursListId = NULL;\n"
            f"  - For all other queries (grades, fees, attendance, etc.), ALWAYS append a filter restricting the query strictly to `UserId = {active_uid}` (or `ApplyAmountToId = {active_uid}`)."
        )
    elif active_role == 3:  # Instructor Role (RoleId = 3)
        system_lines.append(
            "\nCRITICAL ROLE-BASED ACCESS CONTROL (ROLE = INSTRUCTOR, ROLEID = 3):\n"
            "  - Active User: INSTRUCTOR (RoleId = 3).\n"
            "  - Access is scoped to academic performance, classes, and subjects assigned to staff."
        )
    else:  # Admin Role (RoleId = 1)
        system_lines.append(
            "\nCRITICAL ROLE-BASED ACCESS CONTROL (ROLE = ADMIN, ROLEID = 1):\n"
            "  - Active User: ADMIN (RoleId = 1).\n"
            "  - User has full administrative access to query all student records, classes, subjects, and system reports across the entire database."
        )
    if settings.custom_instructions:
        system_lines.append("\nAdditional Custom Rules and Examples:\n" + settings.custom_instructions)
    system = "\n".join(system_lines)
    dbs = ", ".join(f"`{d}`" for d in database_ids)
    user = (
        f"User request:\n{user_request}\n\n"
        f"Allowed database ids: {dbs}\n\n"
        f"Schema (keyword-matched subset):\n{schema_context}\n"
    )

    url = settings.base_url.rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {
        "model": settings.model,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = _auth_headers(settings.base_url)

    with httpx.Client(timeout=120.0) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    usage = data.get("usage", {})
    usage_dict = {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }

    content = data["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise ValueError("Unexpected API response shape")

    try:
        obj = _parse_json_object(content)
    except json.JSONDecodeError:
        fenced = extract_sql_fenced(content)
        if fenced and database_ids:
            return database_ids[0], fenced, content[:2000], usage_dict
        raise

    db_id = str(obj.get("database_id", "")).strip()
    sql = str(obj.get("sql", "")).strip()
    if db_id not in database_ids:
        raise ValueError(f'Model chose unknown database_id "{db_id}"')
    if not sql:
        raise ValueError("Model returned empty sql")
    expl = obj.get("explanation")
    expl_str = str(expl) if expl is not None else None
    return db_id, sql, expl_str, usage_dict
