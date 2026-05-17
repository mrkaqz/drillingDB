"""CLI helper to create the first admin user.

Usage:
    .venv\\Scripts\\python -m drilling_app.create_first_user <username> <password>

If the username already exists the script exits without making changes.
"""
import sys


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python -m drilling_app.create_first_user <username> <password>")
        sys.exit(1)

    username, password = sys.argv[1], sys.argv[2]

    # Import here so the module can be run directly with PYTHONPATH=src
    from drilling_app.db import SessionLocal
    from drilling_app.models import User
    from drilling_app.auth import hash_password

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"User '{username}' already exists — no changes made.")
            sys.exit(0)

        user = User(
            username=username,
            hashed_password=hash_password(password),
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Admin user '{username}' created successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
