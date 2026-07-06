import argparse
import shutil
from datetime import datetime
from pathlib import Path

import db


def backup_database() -> Path | None:
    if not db.DB_PATH.exists():
        return None
    backup_path = db.DB_PATH.with_suffix(f".{datetime.now().strftime('%Y%m%d%H%M%S')}.bak")
    shutil.copy2(db.DB_PATH, backup_path)
    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate local Phase 1-3 lecture data to the Phase 4 schema.")
    parser.add_argument("--assign-to", help="Email of an existing user who should receive unowned legacy lectures.")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating a timestamped SQLite backup first.")
    args = parser.parse_args()

    backup_path = None if args.no_backup else backup_database()
    db.init_db()

    claimed = 0
    if args.assign_to:
        user = db.get_user_by_email(args.assign_to)
        if user is None:
            raise SystemExit(f"No user exists for {args.assign_to}. Create the account first, then rerun this command.")
        claimed = db.assign_legacy_sessions_to_user(int(user["id"]))

    if backup_path:
        print(f"Backup created: {backup_path}")
    print("Schema is up to date.")
    if args.assign_to:
        print(f"Assigned {claimed} legacy lecture(s) to {args.assign_to}.")
    else:
        print("Unowned legacy lectures will be assigned to the first account created.")


if __name__ == "__main__":
    main()
