import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.ENVIRONMENT == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


# create_all jadvallarni YARATADI, lekin mavjud ustunlarni HECH QACHON o'zgartirmaydi.
# Shuning uchun modeldagi tip o'zgarishlari eski bazaga yetib bormaydi (schema drift).
# Patch tarixi: `risk_score.high_risk_tracks` dastlab ARRAY(Integer) edi, keyin JSON'ga
# o'tgan (docs/integration.md #9) — ammo eski bazada hali ham integer[] qolgan edi →
# asyncpg DatatypeMismatchError: "integer[] but expression is of type json".
# `job.job_id` modelda bor, lekin eski bazada yo'q edi — qo'shildi.
_SCHEMA_HEALS = [
    {
        # Faqat ustun hali ham eski ARRAY tipida bo'lsa bajariladi (idempotent).
        "check": """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'risk_score'
              AND column_name = 'high_risk_tracks'
              AND data_type = 'ARRAY'
        """,
        # Eslatma: PG integer[] → jsonb to'g'ridan-to'g'ri cast qilmaydi, to_jsonb() kerak.
        "fix": """
            ALTER TABLE risk_score
            ALTER COLUMN high_risk_tracks TYPE jsonb
            USING to_jsonb(high_risk_tracks)
        """,
    },
    {
        # job jadvalida job_id ustuni yo'qligini tekshirish va qo'shish.
        "check": """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'job'
              AND column_name = 'job_id'
            HAVING COUNT(*) = 0
        """,
        "fix": """
            ALTER TABLE job ADD COLUMN job_id VARCHAR(32)
        """,
    },
]


async def _heal_schemas(conn) -> None:
    """Model ↔ DB tip nomuvofiqliklarini idempotent tuzatish (create_all'dan keyin)."""
    for heal in _SCHEMA_HEALS:
        needs_fix = await conn.scalar(text(heal["check"]))
        if needs_fix is not None:
            await conn.execute(text(heal["fix"]))
            logger.info(
                "Schema heal applied: %s", " ".join(heal["fix"].split())
            )


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Heal alohida tranzaksiyada — xato bo'lsa create_all natijasiga ta'sir qilmasin.
    try:
        async with engine.begin() as conn:
            await _heal_schemas(conn)
            # Clear old demo data (truncate tables) for clean hackathon demo
            await conn.execute(text("""
                TRUNCATE video, event, job, risk_score RESTART IDENTITY CASCADE
            """))
            logger.info("Demo database cleared: video, event, job, risk_score truncated")
    except Exception:
        # Heal muvaffaqiyatsiz bo'lsa ilovani ishga tushirmaymiz — loglaymiz va davom etamiz.
        logger.exception("Schema heal failed — model va DB sxemasi mos emas bo'lishi mumkin")
