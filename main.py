"""
Orchestrator for running two bots: manager_bot and applicant_bot.
Launches them as separate processes and monitors their status.
"""

import os
import sys
import subprocess
import signal
import time
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime

USERS_DATA_DIR = os.getenv("USERS_DATA_DIR", "/tmp/users_data")
logs_dir = Path(USERS_DATA_DIR) / "logs" / "applicant_bot_logs"
logs_dir.mkdir(parents=True, exist_ok=True)

log_filename = logs_dir / f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

file_handler = logging.handlers.RotatingFileHandler(
    log_filename,
    maxBytes=20 * 1024 * 1024,
    backupCount=20,
    encoding='utf-8'
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        file_handler,
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("hrvibe_orchestrator")
logger.info(f"Orchestrator logging configured. Logs written to: {log_filename}")


def start_bot_process(name: str, cwd: str) -> subprocess.Popen:
    logger.info("Starting %s bot in %s", name, cwd)

    if not os.path.isdir(cwd):
        raise FileNotFoundError(f"Directory {cwd} does not exist")

    main_py_path = os.path.join(cwd, "main.py")
    if not os.path.isfile(main_py_path):
        raise FileNotFoundError(f"main.py not found in {cwd}")

    cmd = [sys.executable, "main.py"]

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    logger.info("%s bot started with PID %s", name, proc.pid)
    return proc


def shutdown(procs: list, reason: str):
    logger.info("Shutting down child processes (reason: %s)...", reason)

    for p in procs:
        if p.poll() is None:
            try:
                logger.debug("Terminating process PID %s", p.pid)
                p.terminate()
            except Exception as e:
                logger.warning("Error terminating process PID %s: %s", p.pid, e)

    deadline = time.time() + 30
    for p in procs:
        if p.poll() is None:
            while p.poll() is None and time.time() < deadline:
                time.sleep(0.5)
            if p.poll() is None:
                logger.warning("Process PID %s did not exit in time, killing...", p.pid)
                try:
                    p.kill()
                except Exception as e:
                    logger.warning("Error killing process PID %s: %s", p.pid, e)
            else:
                logger.info("Process PID %s exited with code %s", p.pid, p.poll())

    logger.info("Shutdown completed")


def main():
    project_root = os.path.dirname(os.path.abspath(__file__))
    manager_cwd = os.path.join(project_root, "manager_bot")
    applicant_cwd = os.path.join(project_root, "applicant_bot")

    logger.info("Orchestrator starting...")
    logger.info("Project root: %s", project_root)

    # Проверка USERS_DATA_DIR
    users_data_dir = Path(os.getenv("USERS_DATA_DIR", "/tmp/users_data"))
    try:
        users_data_dir.mkdir(parents=True, exist_ok=True)
        logger.info("USERS_DATA_DIR = %s (created/verified)", users_data_dir)
    except Exception as e:
        logger.error("Failed to create USERS_DATA_DIR %s: %s", users_data_dir, e)
        sys.exit(1)

    manager_proc = None
    applicant_proc = None
    procs = []

    try:
        manager_proc = start_bot_process("manager", manager_cwd)
        procs.append(manager_proc)
        time.sleep(1)

        applicant_proc = start_bot_process("applicant", applicant_cwd)
        procs.append(applicant_proc)

        logger.info("Both bots started successfully")

        shutdown_requested = False

        def handle_sigterm(signum, frame):
            nonlocal shutdown_requested
            if not shutdown_requested:
                shutdown_requested = True
                shutdown(procs, "SIGTERM")
                sys.exit(0)

        def handle_sigint(signum, frame):
            nonlocal shutdown_requested
            if not shutdown_requested:
                shutdown_requested = True
                shutdown(procs, "SIGINT")
                sys.exit(0)

        signal.signal(signal.SIGTERM, handle_sigterm)
        signal.signal(signal.SIGINT, handle_sigint)

        logger.info("Monitoring bot processes...")
        while True:
            manager_code = manager_proc.poll() if manager_proc else None
            applicant_code = applicant_proc.poll() if applicant_proc else None

            if manager_code is not None or applicant_code is not None:
                logger.error("One of the bots exited: manager=%s, applicant=%s", manager_code, applicant_code)
                break

            time.sleep(2)

    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt")
        shutdown(procs, "KeyboardInterrupt")
        sys.exit(0)

    except Exception as e:
        logger.error("Orchestrator error: %s", e, exc_info=True)
        shutdown(procs, "exception")
        sys.exit(1)

    finally:
        if procs:
            shutdown(procs, "main-exit")

    logger.info("Orchestrator exiting")
    sys.exit(1)


if __name__ == "__main__":
    main()
