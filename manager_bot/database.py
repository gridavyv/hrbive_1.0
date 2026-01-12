# manager_bot/database.py
from sqlalchemy import create_engine, Column, Integer, String, Boolean, JSON, BigInteger, TIMESTAMP, ForeignKey, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
import os

# Получаем DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("❌ Переменная окружения DATABASE_URL не задана")

# Fix: Render использует postgresql+psycopg2, но URL может быть с postgres://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Создаём engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Manager(Base):
    __tablename__ = "managers"

    id = Column(BigInteger, primary_key=True)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    first_time_seen = Column(TIMESTAMP(timezone=True), default=func.now())
    privacy_policy_confirmed = Column(Boolean, default=False)
    privacy_policy_confirmation_time = Column(TIMESTAMP(timezone=True))
    access_token_recieved = Column(Boolean, default=False)
    access_token = Column(String)
    access_token_expires_at = Column(TIMESTAMP(timezone=True))
    hh_data = Column(JSON)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())


class Vacancy(Base):
    __tablename__ = "vacancies"

    id = Column(BigInteger, primary_key=True)
    manager_id = Column(BigInteger, ForeignKey("managers.id"), nullable=False)
    name = Column(String)
    vacancy_description_recieved = Column(Boolean, default=False)
    sourcing_criterias_recieved = Column(Boolean, default=False)
    description_json = Column(JSON)
    sourcing_criterias_json = Column(JSON)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(String, primary_key=True)
    vacancy_id = Column(BigInteger, ForeignKey("vacancies.id"), nullable=False)
    manager_id = Column(BigInteger, ForeignKey("managers.id"), nullable=False)
    first_name = Column(String)
    last_name = Column(String)
    phone = Column(String)
    email = Column(String)
    ai_analysis = Column(JSON)
    resume_sorting_status = Column(String, default="new")
    link_to_tg_bot_sent = Column(Boolean, default=False)
    resume_video_received = Column(Boolean, default=False)
    resume_video_path = Column(String)
    resume_recommended = Column(Boolean, default=False)
    resume_accepted = Column(Boolean)
    interview_invitation_sent = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())


def init_db():
    """
    Создаёт таблицы, если их ещё нет.
    Вызывай при старте приложения.
    """
    Base.metadata.create_all(bind=engine)
    print("✅ Таблицы созданы или уже существуют")
