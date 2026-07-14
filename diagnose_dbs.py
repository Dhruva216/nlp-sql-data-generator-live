import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text

# Add src/ to path to allow importing nlp_sql if not installed globally
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from nlp_sql.config import load_config
from nlp_sql.registry import build_engine_for_db

def diagnose():
    print("=== Database Connection Diagnostics ===")
    
    # 1. Load env variables
    load_dotenv(override=True)
    print("Checking environment variables:")
    import os
    mssql_url = os.environ.get("MSSQL_DATABASE_URL")
    print(f"  MSSQL_DATABASE_URL: {mssql_url if mssql_url else 'NOT SET'}")
    print(f"  OPENAI_API_KEY: {'SET' if os.environ.get('OPENAI_API_KEY') else 'NOT SET'}")
    print()

    # 2. Load config.yaml
    try:
        config = load_config()
        print("Successfully loaded config.yaml")
        print("Configured databases:")
        for d in config.databases:
            print(f"  - ID: {d.id}, URI: {d.uri}")
    except Exception as e:
        print(f"ERROR: Failed to load config.yaml: {e}")
        return
    print()

    # 3. Test connections
    print("Testing database connections...")
    for d in config.databases:
        print(f"\nTesting connection for: {d.id}...")
        try:
            engine = build_engine_for_db(d.id, d.uri)
            with engine.connect() as conn:
                res = conn.execute(text("SELECT 1")).scalar()
                print(f"  [SUCCESS] Connected to {d.id} (SELECT 1 returned {res})")
                
                # Test select from UserInfo to check actual data
                if d.id == "mssql_live":
                    print("\nChecking raw data in [dbo].[UserInfo] table:")
                    try:
                        sql = "SELECT TOP 3 UserId, UserName, Password, FirstName, LastName FROM [dbo].[UserInfo]"
                        res_rows = conn.execute(text(sql))
                        cols = list(res_rows.keys())
                        print(f"  Columns: {cols}")
                        for row in res_rows:
                            print(f"  Raw row tuple: {row}")
                            row_dict = {cols[i]: row[i] for i in range(len(cols))}
                            print(f"  Mapped row: {row_dict}")
                    except Exception as ex:
                        print(f"  Could not read UserInfo: {ex}")
        except Exception as e:
            print(f"  [FAILED] Connection failed for {d.id}:")
            print(f"  Error details: {e}")

if __name__ == "__main__":
    diagnose()
