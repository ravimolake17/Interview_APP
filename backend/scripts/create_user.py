"""Create an HR or admin user in the database.

Usage:
  python -m scripts.create_user --email jane@company.com --name "Jane HR" --role HR
  python -m scripts.create_user --email admin2@company.com --name "Admin" --role ADMIN --password 'Secret123'
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import AsyncSessionLocal
from models.user import UserRole
from services.auth_service import AuthService


async def main() -> None:
    parser = argparse.ArgumentParser(description="Create a user in the users table.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True, help="Full name")
    parser.add_argument("--role", choices=["HR", "ADMIN", "SUPERADMIN"], default="HR")
    parser.add_argument("--password", help="If omitted, you will be prompted.")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")
    if len(password) < 6:
        print("Password must be at least 6 characters.", file=sys.stderr)
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        auth = AuthService(db)
        try:
            user = await auth.create_user(
                email=args.email,
                full_name=args.name,
                password=password,
                role=UserRole(args.role),
                acting_admin=SimpleNamespace(role=UserRole.SUPERADMIN),
            )
            await db.commit()
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)

    print(f"Created {user.role.value} user: {user.email} (id={user.id})")


if __name__ == "__main__":
    asyncio.run(main())
