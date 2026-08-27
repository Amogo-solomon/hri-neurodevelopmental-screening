#!/usr/bin/env python3
"""
seed_admin.py — Create the first admin user for the HRI Platform.
Run once after docker compose up:

  docker exec hri_backend python seed_admin.py
  -- or locally --
  cd backend && python seed_admin.py

Environment variables (or .env):
  ADMIN_EMAIL    (default: admin@hri-platform.local)
  ADMIN_NAME     (default: Platform Admin)
  ADMIN_PASSWORD (default: Admin1234!@hri — CHANGE IN PRODUCTION)
"""
import asyncio
import os
import sys

# ── load env ──────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/hri.db")
os.environ.setdefault("SECRET_KEY",   "hri-platform-secret-key-change-in-production")
os.environ.setdefault("UPLOAD_DIR",   "./uploads")
os.environ.setdefault("ENVIRONMENT",  "development")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")

ADMIN_EMAIL    = os.getenv("ADMIN_EMAIL",    "admin@hri-platform.local")
ADMIN_NAME     = os.getenv("ADMIN_NAME",     "Platform Admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin1234!@hri")

# ── bootstrap ─────────────────────────────────────────────────────────────────
from app.db.database import init_db, AsyncSessionLocal
from app.models.models import User
from app.core.security import hash_password
from sqlalchemy import select
from datetime import datetime, timezone


async def seed():
    print("HRI Platform — Admin Seed Script")
    print("=" * 40)

    # Init DB tables
    await init_db()
    print("✓ Database initialised")

    async with AsyncSessionLocal() as db:
        # Check if admin already exists
        result = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"⚠  Admin user already exists: {ADMIN_EMAIL}")
            print(f"   Role: {existing.role} | Active: {existing.is_active}")
            return

        # Create admin user
        admin = User(
            email=ADMIN_EMAIL,
            full_name=ADMIN_NAME,
            hashed_password=hash_password(ADMIN_PASSWORD),
            role="admin",
            is_active=True,
            is_verified=True,
        )
        db.add(admin)
        await db.commit()

        print(f"✓ Admin user created:")
        print(f"  Email    : {ADMIN_EMAIL}")
        print(f"  Password : {ADMIN_PASSWORD}")
        print(f"  Role     : admin")
        print()
        print("⚠  IMPORTANT: Change the default password immediately after first login!")
        print("   Go to: http://localhost:3000/profile → Change Password")
        print()
        print("✓ You can now log in at: http://localhost:3000/login")


if __name__ == "__main__":
    asyncio.run(seed())
