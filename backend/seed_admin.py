"""Quick admin seeder"""
import asyncio
import hashlib
import secrets
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.session import Base
from app.models import DriverAccount

PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 390_000
SALT_BYTES = 16

def _pbkdf2_digest(password: str, salt: bytes, iterations: int) -> str:
	dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
	return dk.hex()

def _hash_password(plain_password: str) -> str:
	salt = secrets.token_bytes(SALT_BYTES)
	digest = _pbkdf2_digest(plain_password, salt, PBKDF2_ITERATIONS)
	return f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${salt.hex()}${digest}"

async def main():
	engine = create_async_engine(settings.DATABASE_URL)
	AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
	
	async with AsyncSessionLocal() as session:
		existing = await session.execute(select(DriverAccount).where(DriverAccount.company_id == "admin"))
		if existing.scalar_one_or_none() is not None:
			print("✓ Admin already exists")
			return
		
		admin = DriverAccount(
			company_id="admin",
			password_hash=_hash_password("123"),
			name="Admin",
			role="Admin",
			is_active=True,
		)
		session.add(admin)
		await session.commit()
		print("✓ Admin user created: admin / 13")

if __name__ == "__main__":
	asyncio.run(main())
