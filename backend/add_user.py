#!/usr/bin/env python3
"""Add a user to MongoDB without a password (for Supabase SSO accounts).

Usage:
    python add_user.py --email you@example.com --name "Your Name" \
                       --role admin --company "Kaduna"
"""
import argparse
import asyncio
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient


async def main(email: str, name: str, role: str, company: str) -> None:
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "insurer_dashboard")
    client = AsyncIOMotorClient(uri)
    db = client[db_name]

    existing = await db["users"].find_one({"email": email})
    if existing:
        if not existing.get("is_active"):
            await db["users"].update_one({"email": email}, {"$set": {"is_active": True}})
            print(f"User {email} already existed but was inactive — re-activated.")
        else:
            print(f"User {email} already exists and is active. Nothing to do.")
        client.close()
        return

    co = await db["companies"].find_one({"name": company})
    if co:
        company_id = co["_id"]
        print(f"Using existing company '{company}'.")
    else:
        result = await db["companies"].insert_one({
            "name": company,
            "code": company.upper()[:10].replace(" ", "_"),
            "contact_email": email,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        })
        company_id = result.inserted_id
        print(f"Company '{company}' created.")

    await db["users"].insert_one({
        "email": email,
        "password_hash": "",
        "name": name,
        "role": role,
        "company_id": company_id,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    })
    print(f"User '{name}' ({email}) added with role '{role}'.")
    client.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--role", default="admin", choices=["admin", "agent", "staff"])
    p.add_argument("--company", default="Kaduna")
    args = p.parse_args()
    asyncio.run(main(args.email, args.name, args.role, args.company))
