# TAGS: [admin]

import logging
import os
from pathlib import Path
from typing import Optional

from telegram import InputFile, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes

logger = logging.getLogger(__name__)

from services.data_service import (
    get_tg_user_data_attribute_from_update_object,
    get_list_of_users_from_records,
    get_target_vacancy_id_from_records,
)
from services.status_validation_service import (
    is_user_in_records,
    is_vacancy_description_recieved,
    is_vacancy_sourcing_criterias_recieved,
    is_vacancy_selected,
    is_vacany_data_enough_for_resume_analysis,
)
from services.questionnaire_service import send_message_to_user
from services.constants import (
    FAIL_TO_IDENTIFY_USER_AS_ADMIN_TEXT,
    FAIL_TECHNICAL_SUPPORT_TEXT,
)

# Import admin-triggered functions from manager_bot
# These are imported here to avoid circular imports - admin.py is imported by main.py,
# not by manager_bot.py, so this is safe
from manager_bot import (
    inform_admin_about_user_readiness,
    define_sourcing_criterias_triggered_by_admin_command,
    send_to_user_sourcing_criterias_triggered_by_admin_command,
    source_negotiations_triggered_by_admin_command,
    source_resumes_triggered_by_admin_command,
    analyze_resume_triggered_by_admin_command,
    update_resume_records_with_fresh_video_from_applicants_triggered_by_admin_command,
    recommend_resumes_triggered_by_admin_command,
)


##########################################
# ------------ ADMIN COMMANDS ------------
##########################################


async def send_message_to_admin(application: Application, text: str, parse_mode: Optional[ParseMode] = None) -> None:
    #TAGS: [admin]

    # ----- GET ADMIN ID from environment variables -----
    
    admin_id = os.getenv("ADMIN_ID", "")
    if not admin_id:
        logger.error("send_message_to_admin:ADMIN_ID environment variable is not set. Cannot send admin notification.")
        return
    
    # ----- SEND NOTIFICATION to admin -----
    
    try:
        if application and application.bot:
            await application.bot.send_message(
                chat_id=int(admin_id),
                text=text,
                parse_mode=parse_mode
            )
            logger.debug(f"send_message_to_admin: Admin notification sent successfully to admin_id: {admin_id}")
        else:
            logger.warning("send_message_to_admin: Cannot send admin notification: application or bot instance not available")
    except Exception as e:
        logger.error(f"send_message_to_admin: Failed to send admin notification: {e}", exc_info=True)


async def admin_get_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    #TAGS: [admin]
    """
    Admin command to list all user IDs from user records.
    Only accessible to users whose ID is in the ADMIN_IDS whitelist.
    """

    try:
        # ----- IDENTIFY USER and pull required data from records -----

        bot_user_id = str(get_tg_user_data_attribute_from_update_object(update=update, tg_user_attribute="id"))
        logger.info(f"admin_get_users_command: started. User_id: {bot_user_id}")
        
        #  ----- CHECK IF USER IS NOT AN ADMIN and STOP if it is -----

        admin_id = os.getenv("ADMIN_ID", "")
        if not admin_id or bot_user_id != admin_id:
            await send_message_to_user(update, context, text=FAIL_TO_IDENTIFY_USER_AS_ADMIN_TEXT)
            logger.error(f"Unauthorized for {bot_user_id}")
            return

        # ----- SEND LIST OF USERS IDs from records -----

        user_ids = get_list_of_users_from_records()

        await send_message_to_user(update, context, text=f"📋 List of users: {user_ids}")
    
    except Exception as e:
        logger.error(f"admin_get_users_command: Failed to execute admin_get_list_of_users command: {e}", exc_info=True)        # Send notification to admin about the error
        if context.application:
            await send_message_to_admin(
                application=context.application,
                text=f"⚠️ Error admin_get_users_command: {e}\nAdmin ID: {bot_user_id if 'bot_user_id' in locals() else 'unknown'}"
            )


async def admin_get_user_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    #TAGS: [admin]
    """
    Admin command to analyze sourcing criterias for all users or a specific user.
    Usage: /admin_analyze_sourcing_criterais [user_id]
    Only accessible to users whose ID is in the ADMIN_IDS whitelist.
    """

    try:
        # ----- IDENTIFY USER and pull required data from records -----

        bot_user_id = str(get_tg_user_data_attribute_from_update_object(update=update, tg_user_attribute="id"))
        logger.info(f"admin_get_user_status_command: started. User_id: {bot_user_id}")

        #  ----- CHECK IF USER IS NOT AN ADMIN and STOP if it is -----

        admin_id = os.getenv("ADMIN_ID", "")
        if not admin_id or bot_user_id != admin_id:
            await send_message_to_user(update, context, text=FAIL_TO_IDENTIFY_USER_AS_ADMIN_TEXT)
            logger.error(f"Unauthorized for {bot_user_id}")
            return

        # ----- PARSE COMMAND ARGUMENTS -----

        target_user_id = None
        if context.args and len(context.args) == 1:
            target_user_id = context.args[0]
            if target_user_id:
                if is_user_in_records(record_id=target_user_id):
                    await inform_admin_about_user_readiness(bot_user_id=target_user_id, application=context.application)
                else:
                    raise ValueError(f"User {target_user_id} not found in records.")
            else:
                raise ValueError(f"Invalid command arguments.")
        else:
            raise ValueError(f"Invalid number of arguments.")
    
    except Exception as e:
        logger.error(f"admin_get_user_status_command: Failed to execute command: {e}", exc_info=True)
        # Send notification to admin about the error
        if context.application:
            await send_message_to_admin(
                application=context.application,
                text=f"⚠️ Error admin_get_user_status_command: {e}\nAdmin ID: {bot_user_id if 'bot_user_id' in locals() else 'unknown'}"
            )


async def admin_anazlyze_sourcing_criterais_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    #TAGS: [admin]
    """
    Admin command to analyze sourcing criterias for all users or a specific user.
    Usage: /admin_analyze_sourcing_criterais [user_id]
    Only accessible to users whose ID is in the ADMIN_IDS whitelist.
    """

    try:
        # ----- IDENTIFY USER and pull required data from records -----

        bot_user_id = str(get_tg_user_data_attribute_from_update_object(update=update, tg_user_attribute="id"))
        logger.info(f"admin_anazlyze_sourcing_criterais_command: started. User_id: {bot_user_id}")

        #  ----- CHECK IF USER IS NOT AN ADMIN and STOP if it is -----

        admin_id = os.getenv("ADMIN_ID", "")
        if not admin_id or bot_user_id != admin_id:
            await send_message_to_user(update, context, text=FAIL_TO_IDENTIFY_USER_AS_ADMIN_TEXT)
            logger.error(f"Unauthorized for {bot_user_id}")
            return

        # ----- PARSE COMMAND ARGUMENTS -----

        target_user_id = None
        if context.args and len(context.args) == 1:
            target_user_id = context.args[0]
            if target_user_id:
                if is_user_in_records(record_id=target_user_id):
                    if is_vacancy_description_recieved(record_id=target_user_id):
                        await define_sourcing_criterias_triggered_by_admin_command(bot_user_id=target_user_id)
                        await send_message_to_user(update, context, text=f"Taks for analysing sourcing criterias is in task_queue for user {target_user_id}.")
                    else:
                        raise ValueError(f"User {target_user_id} does not have vacancy description received.")
                else:
                    raise ValueError(f"User {target_user_id} not found in records.")
            else:
                raise ValueError(f"Invalid command arguments.")
        else:
            raise ValueError(f"Invalid number of arguments.")
    
    except Exception as e:
        logger.error(f"admin_anazlyze_sourcing_criterais_command: Failed to execute command: {e}", exc_info=True)
        # Send notification to admin about the error
        if context.application:
            await send_message_to_admin(
                application=context.application,
                text=f"⚠️ Error admin_anazlyze_sourcing_criterais_command: {e}\nAdmin ID: {bot_user_id if 'bot_user_id' in locals() else 'unknown'}"
            )


async def admin_send_sourcing_criterais_to_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    #TAGS: [admin]
    """
    Admin command to send sourcing criterias to a specific user.
    Usage: /admin_send_sourcing_criterais_to_user [user_id]
    Only accessible to users whose ID is in the ADMIN_IDS whitelist.
    """

    try:
        # ----- IDENTIFY USER and pull required data from records -----

        bot_user_id = str(get_tg_user_data_attribute_from_update_object(update=update, tg_user_attribute="id"))
        logger.info(f"admin_send_sourcing_criterais_to_user_command: started. User_id: {bot_user_id}")

        #  ----- CHECK IF USER IS NOT AN ADMIN and STOP if it is -----

        admin_id = os.getenv("ADMIN_ID", "")
        if not admin_id or bot_user_id != admin_id:
            await send_message_to_user(update, context, text=FAIL_TO_IDENTIFY_USER_AS_ADMIN_TEXT)
            logger.error(f"Unauthorized for {bot_user_id}")
            return

        # ----- PARSE COMMAND ARGUMENTS -----

        target_user_id = None
        if context.args and len(context.args) == 1:
            target_user_id = context.args[0]
            if target_user_id:
                if is_user_in_records(record_id=target_user_id):
                    logger.debug(f"User {target_user_id} found in records.")
                    if is_vacancy_sourcing_criterias_recieved(record_id=target_user_id):
                        await send_to_user_sourcing_criterias_triggered_by_admin_command(bot_user_id=target_user_id, application=context.application)
                        await send_message_to_user(update, context, text=f"Sourcing criterias sent to user {target_user_id}.")
                    else:
                        raise ValueError(f"User {target_user_id} does not have enough vacancy data for resume analysis.")
                else:
                    raise ValueError(f"User {target_user_id} not found in records.")
            else:
                raise ValueError(f"Invalid command arguments.")
        else:
            raise ValueError(f"Invalid number of arguments.")
    
    except Exception as e:
        logger.error(f"admin_send_sourcing_criterais_to_user_command: Failed: {e}", exc_info=True)
        # Send notification to admin about the error
        if context.application:
            await send_message_to_admin(
                application=context.application,
                text=f"⚠️ Error admin_send_sourcing_criterais_to_user_command: {e}\nAdmin ID: {bot_user_id if 'bot_user_id' in locals() else 'unknown'}"
            )


async def admin_update_negotiations_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    #TAGS: [admin]
    """
    Admin command to update negotiations for all users or a specific user.
    Usage: /admin_update_neg_coll_for_all [user_id]
    Only accessible to users whose ID is in the ADMIN_IDS whitelist.
    """

    try:
        # ----- IDENTIFY USER and pull required data from records -----

        bot_user_id = str(get_tg_user_data_attribute_from_update_object(update=update, tg_user_attribute="id"))
        logger.info(f"admin_update_negotiations_command: started. User_id: {bot_user_id}")

        #  ----- CHECK IF USER IS NOT AN ADMIN and STOP if it is -----

        admin_id = os.getenv("ADMIN_ID", "")
        if not admin_id or bot_user_id != admin_id:
            await send_message_to_user(update, context, text=FAIL_TO_IDENTIFY_USER_AS_ADMIN_TEXT)
            logger.error(f"Unauthorized for {bot_user_id}")
            return

        # ----- PARSE COMMAND ARGUMENTS -----

        target_user_id = None
        if context.args and len(context.args) == 1:
            target_user_id = context.args[0]
            if target_user_id:
                if is_user_in_records(record_id=target_user_id):
                    if is_vacancy_selected(record_id=target_user_id):
                        await source_negotiations_triggered_by_admin_command(bot_user_id=target_user_id) # ValueError raised if fails
                        await send_message_to_user(update, context, text=f"Negotiations collection updated for user {target_user_id}.")
                    else:
                        raise ValueError(f"User {target_user_id} does not have enough vacancy data for resume analysis.")
                else:
                    raise ValueError(f"User {target_user_id} not found in records.")
            else:
                raise ValueError(f"Invalid command arguments.")
        else:
            raise ValueError(f"Invalid number of arguments.")
    
    except Exception as e:
        logger.error(f"admin_update_negotiations_command: Failed to execute command: {e}", exc_info=True)
        # Send notification to admin about the error
        if context.application:
            await send_message_to_admin(
                application=context.application,
                text=f"⚠️ Error admin_update_negotiations_command: {e}\nAdmin ID: {bot_user_id if 'bot_user_id' in locals() else 'unknown'}"
            )


async def admin_get_fresh_resumes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    #TAGS: [admin]
    """
    Admin command to get fresh resumes for all users.
    Only accessible to users whose ID is in the ADMIN_IDS whitelist.
    """

    try:
        # ----- IDENTIFY USER and pull required data from records -----

        bot_user_id = str(get_tg_user_data_attribute_from_update_object(update=update, tg_user_attribute="id"))
        logger.info(f"admin_get_fresh_resumes_command: started. User_id: {bot_user_id}")
        
        #  ----- CHECK IF USER IS NOT AN ADMIN and STOP if it is -----

        admin_id = os.getenv("ADMIN_ID", "")
        if not admin_id or bot_user_id != admin_id:
            await send_message_to_user(update, context, text=FAIL_TO_IDENTIFY_USER_AS_ADMIN_TEXT)
            logger.error(f"Unauthorized for {bot_user_id}")
            return

        # ----- PARSE COMMAND ARGUMENTS -----

        target_user_id = None
        if context.args and len(context.args) == 1:
            target_user_id = context.args[0]
            if target_user_id:
                if is_user_in_records(record_id=target_user_id):
                    if is_vacany_data_enough_for_resume_analysis(user_id=target_user_id):
                        await source_resumes_triggered_by_admin_command(bot_user_id=target_user_id)
                        await send_message_to_user(update, context, text=f"Fresh resumes collected for user {target_user_id}.")
                    else:
                        raise ValueError(f"User {target_user_id} does not have enough vacancy data for resume analysis.")
                else:
                    raise ValueError(f"User {target_user_id} not found in records.")
            else:
                raise ValueError(f"Invalid command arguments.")
        else:
            raise ValueError(f"Invalid number of arguments.")

    except Exception as e:
        logger.error(f"admin_get_fresh_resumes_command: Failed to execute command: {e}", exc_info=True)
        # Send notification to admin about the error
        if context.application:
            await send_message_to_admin(
                application=context.application,
                text=f"⚠️ Error admin_get_fresh_resumes_command: {e}\nAdmin ID: {bot_user_id if 'bot_user_id' in locals() else 'unknown'}"
            )


async def admin_anazlyze_resumes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    #TAGS: [admin]
    """
    Admin command to analyze fresh resumes for all users.
    Only accessible to users whose ID is in the ADMIN_IDS whitelist.
    """

    try:
        # ----- IDENTIFY USER and pull required data from records -----

        bot_user_id = str(get_tg_user_data_attribute_from_update_object(update=update, tg_user_attribute="id"))
        logger.info(f"admin_anazlyze_resumes_command: started. User_id: {bot_user_id}")
        
        #  ----- CHECK IF USER IS NOT AN ADMIN and STOP if it is -----

        admin_id = os.getenv("ADMIN_ID", "")
        if not admin_id or bot_user_id != admin_id:
            await send_message_to_user(update, context, text=FAIL_TO_IDENTIFY_USER_AS_ADMIN_TEXT)
            logger.error(f"Unauthorized for {bot_user_id}")
            return

        # ----- PARSE COMMAND ARGUMENTS -----

        target_user_id = None
        if context.args and len(context.args) == 1:
            target_user_id = context.args[0]
            if target_user_id:
                if is_user_in_records(record_id=target_user_id):
                    if is_vacany_data_enough_for_resume_analysis(user_id=target_user_id):
                        await send_message_to_user(update, context, text=f"Start creating tasks for analysis of the fresh resumes for user {target_user_id}.")
                        await analyze_resume_triggered_by_admin_command(bot_user_id=target_user_id)
                        await send_message_to_user(update, context, text=f"Analysis of fresh resumes is done for user {target_user_id}.")
                    else:
                        raise ValueError(f"User {target_user_id} does not have enough vacancy data for resume analysis.")
                else:
                    raise ValueError(f"User {target_user_id} not found in records.")
            else:
                raise ValueError(f"Invalid command arguments.")
        else:
            raise ValueError(f"Invalid number of arguments.")
    
    except Exception as e:
        logger.error(f"admin_anazlyze_resumes_command: Failed to execute command: {e}", exc_info=True)
        # Send notification to admin about the error
        if context.application:
            await send_message_to_admin(
                application=context.application,
                text=f"⚠️ Error admin_anazlyze_resumes_command: {e}\nAdmin ID: {bot_user_id if 'bot_user_id' in locals() else 'unknown'}"
            )


async def admin_update_resume_records_with_applicants_video_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    #TAGS: [admin]
    """
    Admin command to update resume records with fresh videos from applicants for all users.
    Only accessible to users whose ID is in the ADMIN_IDS whitelist.
    """

    try:
        # ----- IDENTIFY USER and pull required data from records -----

        bot_user_id = str(get_tg_user_data_attribute_from_update_object(update=update, tg_user_attribute="id"))
        logger.info(f"admin_update_resume_records_with_applicants_video_status_command: started. User_id: {bot_user_id}")

        #  ----- CHECK IF USER IS NOT AN ADMIN and STOP if it is -----

        admin_id = os.getenv("ADMIN_ID", "")
        if not admin_id or bot_user_id != admin_id:
            await send_message_to_user(update, context, text=FAIL_TO_IDENTIFY_USER_AS_ADMIN_TEXT)
            logger.error(f"Unauthorized for {bot_user_id}")
            return

        # ----- PARSE COMMAND ARGUMENTS -----

        target_user_id = None
        if context.args and len(context.args) == 1:
            target_user_id = context.args[0]
            if target_user_id:
                if is_user_in_records(record_id=target_user_id):
                    if is_vacany_data_enough_for_resume_analysis(user_id=target_user_id):
                        target_user_vacancy_id = get_target_vacancy_id_from_records(record_id=target_user_id)
                        await update_resume_records_with_fresh_video_from_applicants_triggered_by_admin_command(bot_user_id=target_user_id, vacancy_id=target_user_vacancy_id)
                        await send_message_to_user(update, context, text=f"Resume records updated with fresh videos from applicants for user {target_user_id}.")
                    else:
                        raise ValueError(f"User {target_user_id} does not have enough vacancy data for resume analysis.")
                else:
                    raise ValueError(f"User {target_user_id} not found in records.")
            else:
                raise ValueError(f"Invalid command arguments.")
        else:
            raise ValueError(f"Invalid number of arguments.")

    
    except Exception as e:
        logger.error(f"admin_update_resume_records_with_applicants_video_status_command: Failed to execute command: {e}", exc_info=True)
        # Send notification to admin about the error
        if context.application:
            await send_message_to_admin(
                application=context.application,
                text=f"⚠️ Error admin_update_resume_records_with_applicants_video_status_command: {e}\nAdmin ID: {bot_user_id if 'bot_user_id' in locals() else 'unknown'}"
            ) 


async def admin_recommend_resumes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    #TAGS: [admin]
    """
    Admin command to recommend applicants with video for all users.
    Only accessible to users whose ID is in the ADMIN_IDS whitelist.
    """

    try:
        # ----- IDENTIFY USER and pull required data from records -----

        bot_user_id = str(get_tg_user_data_attribute_from_update_object(update=update, tg_user_attribute="id"))
        logger.info(f"admin_recommend_resumes_command: started. User_id: {bot_user_id}")
        
        #  ----- CHECK IF USER IS NOT AN ADMIN and STOP if it is -----

        admin_id = os.getenv("ADMIN_ID", "")
        if not admin_id or bot_user_id != admin_id:
            await send_message_to_user(update, context, text=FAIL_TO_IDENTIFY_USER_AS_ADMIN_TEXT)
            logger.error(f"Unauthorized for {bot_user_id}")
            return

        # ----- PARSE COMMAND ARGUMENTS -----

        target_user_id = None
        if context.args and len(context.args) == 1:
            target_user_id = context.args[0]
            if target_user_id:
                if is_user_in_records(record_id=target_user_id):
                    if is_vacany_data_enough_for_resume_analysis(user_id=target_user_id):
                        await recommend_resumes_triggered_by_admin_command(bot_user_id=target_user_id, application=context.application)
                        await send_message_to_user(update, context, text="Recommending resumes is triggered for user {target_user_id}.")
                    else:
                        raise ValueError(f"User {target_user_id} does not have enough vacancy data for resume analysis.")
                else:
                    raise ValueError(f"User {target_user_id} not found in records.")
            else:
                raise ValueError(f"Invalid command arguments.")
        else:
            raise ValueError(f"Invalid number of arguments.")
    
    except Exception as e:
        logger.error(f"admin_recommend_resumes_command: Failed to execute command: {e}", exc_info=True)
        # Send notification to admin about the error
        if context.application:
            await send_message_to_admin(
                application=context.application,
                text=f"⚠️ Error admin_recommend_resumes_command: {e}\nAdmin ID: {bot_user_id if 'bot_user_id' in locals() else 'unknown'}"
            )


async def admin_send_message_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    #TAGS: [admin]
    """
    Admin command to send a message to a specific user by user_id (chat_id).
    Usage: /admin_send_message <user_id> <message_text>
    Usage example: /admin_send_message 7853115214 Привет! Как дела?
    Sends notification to admin if fails
    """
    
    try:
        # ----- IDENTIFY USER and pull required data from records -----

        bot_user_id = str(get_tg_user_data_attribute_from_update_object(update=update, tg_user_attribute="id"))
        logger.info(f"admin_send_message_command triggered by user_id: {bot_user_id}")
        
        #  ----- CHECK IF USER IS NOT AN ADMIN and STOP if it is -----

        admin_id = os.getenv("ADMIN_ID", "")
        if not admin_id or bot_user_id != admin_id:
            await send_message_to_user(update, context, text=FAIL_TO_IDENTIFY_USER_AS_ADMIN_TEXT)
            logger.error(f"Unauthorized for {bot_user_id}")
            return

        # ----- PARSE COMMAND ARGUMENTS -----

        if not context.args or len(context.args) < 2:
            raise ValueError(f"Invalid number of arguments.")
        
        target_user_id = context.args[0]
        message_text = " ".join(context.args[1:])  # Join all remaining arguments as message text

        # ----- VALIDATE USER_ID -----

        try:
            target_user_id_int = int(target_user_id)
        except ValueError:
            raise ValueError(f"Invalid command arguments.")

        # ----- SEND MESSAGE TO USER -----

        if context.application and context.application.bot:
            try:
                await context.application.bot.send_message(
                    chat_id=target_user_id_int,
                    text=message_text
                )
                await send_message_to_user(update, context, text=f"✅ Сообщение отправлено пользователю {target_user_id}:\n'{message_text}'")
                logger.info(f"Admin {bot_user_id} sent message to user {target_user_id}: {message_text}")
            except Exception as send_err:
                error_msg = f"❌ Не удалось отправить сообщение пользователю {target_user_id}: {send_err}"
                await send_message_to_user(update, context, text=error_msg)
                logger.error(f"Failed to send message to user {target_user_id}: {send_err}", exc_info=True)
                raise
        else:
            raise ValueError("Application or bot instance not available")
    
    except Exception as e:
        logger.error(f"Failed to execute admin_send_message_to_user command: {e}", exc_info=True)
        await send_message_to_user(update, context, text=FAIL_TECHNICAL_SUPPORT_TEXT)
        # Send notification to admin about the error
        if context.application:
            await send_message_to_admin(
                application=context.application,
                text=f"⚠️ Error executing admin_send_message_to_user command: {e}\nAdmin ID: {bot_user_id if 'bot_user_id' in locals() else 'unknown'}"
            )


async def admin_pull_file_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    #TAGS: [admin]
    """
    Admin command to pull and send log files.
    Usage: /admin_pull_file <file_relative_path>
    Usage example: /admin_pull_file logs/manager_bot_logs/1234432.log
    Sends the log file as a document to the admin chat.
    """
    
    try:
        # ----- IDENTIFY USER and pull required data from records -----

        bot_user_id = str(get_tg_user_data_attribute_from_update_object(update=update, tg_user_attribute="id"))
        logger.info(f"admin_pull_file_command: started. User_id: {bot_user_id}")
        
        #  ----- CHECK IF USER IS NOT AN ADMIN and STOP if it is -----

        admin_id = os.getenv("ADMIN_ID", "")
        if not admin_id or bot_user_id != admin_id:
            await send_message_to_user(update, context, text=FAIL_TO_IDENTIFY_USER_AS_ADMIN_TEXT)
            logger.error(f"Unauthorized for {bot_user_id}")
            return

        # ----- PARSE COMMAND ARGUMENTS -----

        if not context.args or len(context.args) != 1:
            raise ValueError(f"Invalid number of arguments.")
        
        file_relative_path = context.args[0]

        # ----- CONSTRUCT LOG FILE PATH -----

        data_dir = Path(os.getenv("USERS_DATA_DIR", "/users_data"))
        file_path = data_dir / file_relative_path
        file_name = file_path.name

        # ----- VALIDATE FILE EXTENSION -----

        valid_extensions = [".log", ".json", ".mp4"]
        file_extension = file_path.suffix
        if file_extension not in valid_extensions:
            invalid_extension_text = f"Invalid file extension.\nValid: {', '.join(valid_extensions)}"
            raise ValueError(invalid_extension_text)

        # ----- CHECK IF FILE EXISTS -----

        if not file_path.exists():
            invalid_path_text = f"Invalid file relative path'{file_relative_path}'. File not found"
            raise FileNotFoundError(invalid_path_text)

        # ----- SEND LOG FILE TO USER -----

        if context.application and context.application.bot:
            try:
                chat_id = update.effective_chat.id
                with open(file_path, 'rb') as file:
                    await context.application.bot.send_document(
                        chat_id=chat_id,
                        document=InputFile(file, filename=file_name)
                    )
                logger.info(f"admin_pull_file_command: file '{file_path}' sent to user {bot_user_id}")
            except Exception as send_err:
                raise TelegramError(f"Failed to send file '{file_path}': {send_err}")
        else:
            raise RuntimeError("Application or bot instance not available")
    except Exception as e:
        logger.error(f"admin_pull_file_command: Failed to execute: {e}", exc_info=True)
        # Send notification to admin about the error
        if context.application:
            await send_message_to_admin(
                application=context.application,
                text=f"⚠️ Error admin_pull_file_command: {e}\nAdmin ID: {bot_user_id if 'bot_user_id' in locals() else 'unknown'}"
            )

