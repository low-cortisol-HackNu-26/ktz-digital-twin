# SQLAlchemy async engine and session factory.
#
# engine: AsyncEngine
#   Created from settings.DATABASE_URL
#   pool_size=10, max_overflow=20, pool_pre_ping=True
#
# AsyncSessionLocal: async_sessionmaker
#   bind=engine, expire_on_commit=False
#
# get_session() -> AsyncGenerator[AsyncSession, None]
#   Used as FastAPI dependency (also imported in deps.py as get_db)
#   Yields session, commits on exit, rolls back on exception, closes after
#
# Base: DeclarativeBase   (imported by all models)
