"""
migrate_running_state.py — Add 'Running' state to agent_log constraint
This migration allows agents to log when they START processing, not just when they finish.
Run from the command_center/ directory: python migrate_running_state.py
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

DB_HOST     = os.getenv("DB_HOST",     "35.234.215.116")
DB_PORT     = int(os.getenv("DB_PORT", "5432"))
DB_USER     = os.getenv("DB_USER",     "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME     = os.getenv("DB_NAME",     "talos_app")

MIGRATION_SQL = """
-- Drop the old constraint
ALTER TABLE agent_log DROP CONSTRAINT IF EXISTS agent_log_lifecycle_state_check;

-- Add the new constraint with 'Running' included
ALTER TABLE agent_log ADD CONSTRAINT agent_log_lifecycle_state_check 
    CHECK (lifecycle_state IN ('Running', 'Pending', 'Executed', 'Rejected'));
"""

def run_migration():
    print("[TALOS] Running Migration: Add 'Running' State")
    print("=" * 60)
    
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER,
        password=DB_PASSWORD, dbname=DB_NAME,
        sslmode="require", connect_timeout=10,
    )
    
    try:
        with conn.cursor() as cur:
            print("\n> Dropping old constraint...")
            cur.execute("ALTER TABLE agent_log DROP CONSTRAINT IF EXISTS agent_log_lifecycle_state_check;")
            print("[OK] Old constraint dropped")
            
            print("\n> Adding new constraint with 'Running' state...")
            cur.execute("""
                ALTER TABLE agent_log ADD CONSTRAINT agent_log_lifecycle_state_check 
                    CHECK (lifecycle_state IN ('Running', 'Pending', 'Executed', 'Rejected'));
            """)
            print("[OK] New constraint added")
            
            print("\n> Verifying constraint...")
            cur.execute("""
                SELECT conname, pg_get_constraintdef(oid) 
                FROM pg_constraint 
                WHERE conrelid = 'agent_log'::regclass 
                  AND conname = 'agent_log_lifecycle_state_check';
            """)
            result = cur.fetchone()
            if result:
                print(f"[OK] Constraint verified: {result[0]}")
                print(f"     Definition: {result[1]}")
            
        conn.commit()
        print("\n[SUCCESS] Migration completed successfully!")
        print("The agent_log table now accepts 'Running' state.")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Migration failed: {e}")
        raise e
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()

# Made with Bob
