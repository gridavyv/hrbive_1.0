import asyncio
import logging
import os

from manager_bot import (
    create_manager_application,
    ai_task_queue,
    start_command,
)
from admin import (
    admin_get_managers_command,
    admin_get_manager_status_command,
    admin_update_negotiations_command,
    admin_get_fresh_resumes_command,
    admin_anazlyze_resumes_command,
    admin_analyze_sourcing_criterais_command,
    admin_send_sourcing_criterais_to_user_command,
    admin_update_resume_records_with_applicants_video_status_command,
    admin_recommend_resumes_command,
    admin_send_message_command,
    admin_pull_file_command,
)
from services.data_service import (
    create_data_directory,
    create_users_records_file,
)
from services.constants import (
    BTN_MENU,
    BTN_FEEDBACK,
    WELCOME_TEXT_WHEN_STARTING_BOT,
)
from services.logging_service import setup_logging
from telegram.ext import CommandHandler
from manager_bot.config import TELEGRAM_MANAGER_BOT_TOKEN

logger = logging.getLogger(__name__)

# ----------- MENU -------------
from telegram.ext import ReplyKeyboardMarkup, KeyboardButton

BOTTOM_MENU_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(BTN_MENU), KeyboardButton(BTN_FEEDBACK)]
    ],
    resize_keyboard=True,
    is_persistent=True,
)


async def _show_bottom_menu_on_start(update, context):
    if update.effective_message:
        await update.effective_message.reply_text(WELCOME_TEXT_WHEN_STARTING_BOT, reply_markup=BOTTOM_MENU_KB)
        await start_command(update, context)


# ----------- GLOBAL SHUTDOWN FLAG -----------
_shutting_down = False


async def run_manager_bot() -> None:
    global _shutting_down

    application = create_manager_application(TELEGRAM_MANAGER_BOT_TOKEN)
    application.add_handler(CommandHandler("start", _show_bottom_menu_on_start), group=-1)

    # Admin handlers
    application.add_handler(CommandHandler("admin_get_managers", admin_get_managers_command))
    application.add_handler(CommandHandler("admin_get_manager_status", admin_get_manager_status_command))
    application.add_handler(CommandHandler("admin_analyze_criterias", admin_analyze_sourcing_criterais_command))
    application.add_handler(CommandHandler("admin_send_criterias_to_user", admin_send_sourcing_criterais_to_user_command))
    application.add_handler(CommandHandler("admin_update_neg_coll", admin_update_negotiations_command))
    application.add_handler(CommandHandler("admin_get_fresh_resumes", admin_get_fresh_resumes_command))
    application.add_handler(CommandHandler("admin_analyze_resumes", admin_anazlyze_resumes_command))
    application.add_handler(CommandHandler("admin_update_videos", admin_update_resume_records_with_applicants_video_status_command))
    application.add_handler(CommandHandler("admin_recommend", admin_recommend_resumes_command))
    application.add_handler(CommandHandler("admin_send_message", admin_send_message_command))
    application.add_handler(CommandHandler("admin_pull_file", admin_pull_file_command))

    ai_task_queue.start_worker()
    logger.info("Task queue worker to process AI related tasks is started.")

    await application.initialize()
    await application.start()

    try:
        await application.updater.start_polling()
        logger.info("Bot is now polling for updates. Press Ctrl+C to stop.")
        await asyncio.Event().wait()

    except (KeyboardInterrupt, asyncio.CancelledError):
        if not _shutting_down:
            _shutting_down = True
    finally:
        if _shutting_down:
            logger.info("\nApplication is shutting down gracefully...")

            try:
                await ai_task_queue.stop_worker(wait=True)
                logger.info("Task queue worker that processes AI related tasks is stopped.")
            except Exception as e:
                logger.error(f"Error stopping task queue worker: {e}")

            try:
                await application.updater.stop()
            except Exception:
                pass
            try:
                await application.stop()
            except Exception:
                pass
            try:
                await application.shutdown()
            except Exception:
                pass

            logger.info("Application graceful shut down is completed.")


def main():
    setup_logging()
    logger.info("Telegram Bot for Managers is running")

    create_users_records_file()

    try:
        asyncio.run(run_manager_bot())
    except KeyboardInterrupt:
        logger.info("\nTelegram Bot for Managers has been stopped by user.")


if __name__ == "__main__":
    main()
