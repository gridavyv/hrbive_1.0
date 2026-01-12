# manager_bot/services/data_service.py
# TAGS: [status_validation], [get_data], [create_data], [update_data], [directory_path], [file_path], [persistent_keyboard], [format_data]

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from telegram import Update

from manager_bot.config import *
from database import SessionLocal, Manager, Vacancy, Resume
from services.constants import (
    BOT_FOR_APPLICANTS_USERNAME,
    AUTH_REQ_TEXT,
    AUTH_SUCCESS_TEXT,
    AUTH_FAILED_TEXT,
    PRIVACY_POLICY_CONFIRMATION_TEXT,
    SUCCESS_TO_GET_PRIVACY_POLICY_CONFIRMATION_TEXT,
    MISSING_PRIVACY_POLICY_CONFIRMATION_TEXT,
    MISSING_VACANCY_SELECTION_TEXT,
    RESUME_PASSED_SCORE,
    INVITE_TO_INTERVIEW_CALLBACK_PREFIX,
    APPLICANT_INTERVIEW_INVITATION_TEXT,
    APPLICANT_REJECTION_INTERVIEW_INVITATION_TEXT,
    FEEDBACK_REQUEST_TEXT,
    FEEDBACK_SENT_TEXT,
    WELCOME_VIDEO_RECORD_REQUEST_TEXT,
    VIDEO_SENDING_CONFIRMATION_TEXT,
    MISSING_VIDEO_RECORD_TEXT,
)
from manager_bot.config import HH_CLIENT_ID, OAUTH_REDIRECT_URL

logger = logging.getLogger(__name__)


# ****** [create_data] ******

def create_record_for_new_user_in_records(record_id: str) -> None:
    db = SessionLocal()
    try:
        if db.query(Manager).filter(Manager.id == int(record_id)).first():
            logger.debug(f"Manager {record_id} уже существует.")
            return
        manager = Manager(
            id=int(record_id),
            first_time_seen=datetime.now(timezone.utc),
            privacy_policy_confirmed=False,
            access_token_recieved=False,
            vacancy_selected=False,
            vacancy_description_recieved=False,
            vacancy_sourcing_criterias_recieved=False
        )
        db.add(manager)
        db.commit()
        logger.debug(f"Пользователь {record_id} добавлен в БД")
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при создании пользователя {record_id}: {e}")
        raise
    finally:
        db.close()


def create_record_for_new_resume_id_in_resume_records(bot_user_id: str, vacancy_id: str, resume_record_id: str) -> None:
    db = SessionLocal()
    try:
        if db.query(Resume).filter(Resume.id == resume_record_id).first():
            logger.debug(f"Резюме {resume_record_id} уже существует.")
            return
        vacancy_name = get_target_vacancy_name_from_records(record_id=bot_user_id)
        resume = Resume(
            id=resume_record_id,
            vacancy_id=int(vacancy_id),
            manager_id=int(bot_user_id),
            vacancy_name=vacancy_name,
            resume_sorting_status="new"
        )
        db.add(resume)
        db.commit()
        logger.info(f"Резюме {resume_record_id} добавлено в БД")
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при добавлении резюме {resume_record_id}: {e}")
        raise
    finally:
        db.close()


def create_oauth_link(state: str) -> str:
    """Генерирует ссылку для авторизации на HH."""
    if not HH_CLIENT_ID:
        raise ValueError("HH_CLIENT_ID не задан")
    if not OAUTH_REDIRECT_URL:
        raise ValueError("OAUTH_REDIRECT_URL не задан")
    return (
        f"https://hh.ru/oauth/authorize?response_type=code"
        f"&client_id={HH_CLIENT_ID}"
        f"&state={state}"
        f"&redirect_uri={OAUTH_REDIRECT_URL}"
    )


def create_tg_bot_link_for_applicant(bot_user_id: str, vacancy_id: str, resume_id: str) -> str:
    payload = f"{bot_user_id}_{vacancy_id}_{resume_id}"
    return f"https://t.me/{BOT_FOR_APPLICANTS_USERNAME}?start={payload}"


# ****** [get_data] ******

def get_access_token_from_records(bot_user_id: str) -> Optional[str]:
    db = SessionLocal()
    try:
        manager = db.query(Manager).filter(Manager.id == int(bot_user_id)).first()
        return manager.access_token if manager else None
    except Exception as e:
        logger.error(f"Ошибка получения access_token для {bot_user_id}: {e}")
        return None
    finally:
        db.close()


def get_target_vacancy_id_from_records(record_id: str) -> Optional[str]:
    db = SessionLocal()
    try:
        manager = db.query(Manager).filter(Manager.id == int(record_id)).first()
        if manager and manager.vacancy_selected:
            return str(manager.vacancy_id)
        return None
    except Exception as e:
        logger.error(f"Ошибка получения ID вакансии для {record_id}: {e}")
        return None
    finally:
        db.close()


def get_target_vacancy_name_from_records(record_id: str) -> Optional[str]:
    db = SessionLocal()
    try:
        manager = db.query(Manager).filter(Manager.id == int(record_id)).first()
        return manager.vacancy_name if manager and manager.vacancy_name else None
    except Exception as e:
        logger.error(f"Ошибка получения названия вакансии для {record_id}: {e}")
        return None
    finally:
        db.close()


def get_list_of_resume_ids_for_recommendation(bot_user_id: str, vacancy_id: str) -> List[str]:
    db = SessionLocal()
    try:
        resumes = db.query(Resume).filter(
            Resume.vacancy_id == int(vacancy_id),
            Resume.resume_sorting_status == "passed",
            Resume.resume_video_received == True,
            Resume.resume_recommended == False
        ).all()
        return [r.id for r in resumes]
    except Exception as e:
        logger.error(f"Ошибка получения ID резюме для рекомендации: {e}")
        return []
    finally:
        db.close()


def get_resume_recommendation_text_from_resume_records(bot_user_id: str, vacancy_id: str, resume_record_id: str) -> str:
    db = SessionLocal()
    try:
        resume = db.query(Resume).filter(Resume.id == resume_record_id).first()
        if not resume or not resume.ai_analysis:
            raise ValueError(f"Нет данных для резюме {resume_record_id}")

        first_name = resume.first_name or ""
        last_name = resume.last_name or ""
        final_score = resume.ai_analysis.get("final_score", 0)
        recommendation = resume.ai_analysis.get("recommendation", "")
        attention = resume.ai_analysis.get("requirements_compliance", {}).get("attention", [])

        attention_text = "\n".join(f"- {item}" for item in attention) if isinstance(attention, list) else str(attention)

        return (
            f"<b>Имя</b>: {first_name} {last_name}\n"
            f"<b>Общий балл</b>: <b>{final_score}</b> из 10\n"
            f"--------------------\n"
            f"<b>Рекомендация:</b>\n{recommendation}\n"
            f"--------------------\n"
            f"<b>Обратить внимание:</b>\n{attention_text}"
        )
    except Exception as e:
        logger.error(f"Ошибка генерации текста для резюме {resume_record_id}: {e}")
        raise
    finally:
        db.close()


def get_path_to_video_from_applicant_from_resume_records(bot_user_id: str, vacancy_id: str, resume_record_id: str) -> Path:
    db = SessionLocal()
    try:
        resume = db.query(Resume).filter(Resume.id == resume_record_id).first()
        if not resume or not resume.resume_video_path:
            raise ValueError(f"Путь к видео не найден для резюме {resume_record_id}")
        return Path(resume.resume_video_path)
    except Exception as e:
        logger.error(f"Ошибка получения пути к видео {resume_record_id}: {e}")
        raise
    finally:
        db.close()


def get_employer_id_from_records(record_id: str) -> Optional[str]:
    db = SessionLocal()
    try:
        manager = db.query(Manager).filter(Manager.id == int(record_id)).first()
        if manager and manager.hh_data:
            return str(manager.hh_data.get("employer", {}).get("id"))
        return None
    except Exception as e:
        logger.error(f"Ошибка получения employer_id для {record_id}: {e}")
        return None
    finally:
        db.close()


def get_list_of_users_from_records() -> List[str]:
    db = SessionLocal()
    try:
        managers = db.query(Manager).all()
        return [str(m.id) for m in managers]
    except Exception as e:
        logger.error(f"Ошибка получения списка пользователей: {e}")
        return []
    finally:
        db.close()


def get_user_name_from_records(record_id: str) -> Optional[str]:
    db = SessionLocal()
    try:
        manager = db.query(Manager).filter(Manager.id == int(record_id)).first()
        if manager:
            name = f"{manager.first_name or ''} {manager.last_name or ''}".strip()
            return name if name else None
        return None
    except Exception as e:
        logger.error(f"Ошибка получения имени пользователя {record_id}: {e}")
        return None
    finally:
        db.close()


# ****** [update_data] ******

def update_user_records_with_top_level_key(record_id: int | str, key: str, value: str | int | bool | dict | list) -> None:
    db = SessionLocal()
    try:
        manager = db.query(Manager).filter(Manager.id == int(record_id)).first()
        if not manager:
            raise ValueError(f"Пользователь {record_id} не найден")
        if hasattr(Manager, key):
            setattr(manager, key, value)
            db.commit()
            logger.info(f"Обновлено: {key} = {value} для {record_id}")
        else:
            raise ValueError(f"Поле {key} не существует в Manager")
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка обновления пользователя {record_id}: {e}")
        raise
    finally:
        db.close()


def update_resume_record_with_top_level_key(bot_user_id: str, vacancy_id: str, resume_record_id: str, key: str, value: str | int | bool | dict | list) -> None:
    db = SessionLocal()
    try:
        resume = db.query(Resume).filter(Resume.id == resume_record_id).first()
        if not resume:
            raise ValueError(f"Резюме {resume_record_id} не найдено")
        if hasattr(Resume, key):
            setattr(resume, key, value)
            db.commit()
            logger.info(f"Обновлено: {key} = {value} для резюме {resume_record_id}")
        else:
            raise ValueError(f"Поле {key} не существует в Resume")
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка обновления резюме {resume_record_id}: {e}")
        raise
    finally:
        db.close()


# ****** [persistent_keyboard] ******

def get_persistent_keyboard_messages(bot_user_id: str) -> List[tuple[int, int]]:
    return []

def add_persistent_keyboard_message(bot_user_id: str, chat_id: int, message_id: int) -> None:
    pass

def remove_persistent_keyboard_message(bot_user_id: str, chat_id: int, message_id: int) -> None:
    pass

def clear_all_persistent_keyboard_messages(bot_user_id: str) -> None:
    pass


# ****** [format_data] ******

def format_oauth_link_text(oauth_link: str) -> str:
    return f"<a href=\"{oauth_link}\">Ссылка для авторизации</a>"
# main.py
from telegram.ext import Application
from manager_bot.config import TELEGRAM_MANAGER_BOT_TOKEN
from manager_bot.database import init_db


def main():
    # Проверка всех переменных
    try:
        print("✅ Все переменные окружения загружены")
    except ValueError as e:
        print(f"🛑 Ошибка: {e}")
        return

    # Инициализация БД
    init_db()

    # Запуск бота
    app = Application.builder().token(TELEGRAM_MANAGER_BOT_TOKEN).build()

    # Подключи свои хендлеры
    # setup_handlers(app)

    print("🚀 Бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
