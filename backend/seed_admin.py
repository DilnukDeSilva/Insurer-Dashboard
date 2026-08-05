#!/usr/bin/env python3
"""Run once to bootstrap the first admin user and company.

Usage:
    cd backend
    source .venv/bin/activate
    python seed_admin.py
"""
import asyncio
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def main() -> None:
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "insurer_dashboard")

    client = AsyncIOMotorClient(uri)
    db = client[db_name]

    print("=== Insurer Dashboard — Admin Seed ===")
    email = input("Email: ").strip()
    name = input("Full name: ").strip()
    password = input("Password: ").strip()
    company_name = input("Company name (e.g. Allianz Insurance Lanka Limited): ").strip()
    company_code = input("Company code (short identifier, e.g. ALLIANZ): ").strip().upper()

    if await db["users"].find_one({"email": email}):
        print(f"User {email} already exists.")
        client.close()
        return

    # Create or reuse company
    existing_company = await db["companies"].find_one({"name": company_name})
    if existing_company:
        company_id = existing_company["_id"]
        print(f"Company '{company_name}' already exists, reusing it.")
    else:
        result = await db["companies"].insert_one({
            "name": company_name,
            "code": company_code,
            "contact_email": email,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        })
        company_id = result.inserted_id
        print(f"Company '{company_name}' created.")

    await db["users"].insert_one({
        "email": email,
        "password_hash": pwd.hash(password),
        "name": name,
        "role": "admin",
        "company_id": company_id,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    })

    print(f"\nAdmin user '{name}' ({email}) created successfully.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
