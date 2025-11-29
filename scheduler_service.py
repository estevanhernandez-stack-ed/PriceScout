import os
import sys
import json
import glob
from datetime import datetime, time
import pytz
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from azure.servicebus import ServiceBusClient, ServiceBusMessage

# Add project root to path to allow imports from the 'app' package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app import config

logger = logging.getLogger(__name__)

def send_scrape_task_to_queue(task_config: dict, company_name: str):
    """
    Sends a scrape task to the Azure Service Bus queue.

    Args:
        task_config (dict): The configuration dictionary for the task.
        company_name (str): The name of the company this task belongs to.
    """
    connection_str = config.AZURE_SERVICE_BUS_CONNECTION_STRING
    queue_name = 'scrape-jobs'

    if not connection_str:
        logger.error("Azure Service Bus connection string is not configured. Cannot send task.")
        return

    try:
        with ServiceBusClient.from_connection_string(connection_str) as client:
            with client.get_queue_sender(queue_name) as sender:
                message_body = {
                    "task_config": task_config,
                    "company_name": company_name,
                }
                message = ServiceBusMessage(json.dumps(message_body))
                sender.send_messages(message)
                logger.info(f"Sent task '{task_config['task_name']}' for company '{company_name}' to queue '{queue_name}'.")
    except Exception as e:
        logger.error(f"Failed to send task to Service Bus: {e}", exc_info=True)


def check_and_run_tasks():
    """Scans all company task directories and sends any due tasks to the queue."""
    logger.info("Checking for scheduled tasks...")

    company_dirs = glob.glob(os.path.join(config.DATA_DIR, '*'))

    for company_dir in company_dirs:
        if not os.path.isdir(company_dir):
            continue

        company_name = os.path.basename(company_dir)
        tasks_dir = os.path.join(company_dir, 'scheduled_tasks')

        if not os.path.exists(tasks_dir):
            continue

        for task_file in glob.glob(os.path.join(tasks_dir, '*.json')):
            try:
                with open(task_file, 'r+') as f:
                    task_config = json.load(f)

                    if not task_config.get('enabled', False):
                        continue

                    now_utc = datetime.now(pytz.utc)
                    schedule_time = time.fromisoformat(task_config.get('schedule_time_utc', '00:00'))

                    is_correct_day = True
                    if 'day_of_week' in task_config:
                        day_map = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
                        scheduled_day_name = task_config['day_of_week']
                        if day_map.get(scheduled_day_name) != now_utc.weekday():
                            is_correct_day = False

                    if is_correct_day and now_utc.hour == schedule_time.hour and now_utc.minute == schedule_time.minute:
                        last_run_dt = datetime.fromisoformat(task_config['last_run']) if task_config.get('last_run') else None

                        if not last_run_dt or (now_utc - last_run_dt).total_seconds() > 60:
                            send_scrape_task_to_queue(task_config, company_name)
                            
                            task_config['last_run'] = now_utc.isoformat()
                            f.seek(0)
                            json.dump(task_config, f, indent=4)
                            f.truncate()
            except Exception as e:
                logger.error(f"Failed to process task file {task_file}: {e}", exc_info=True)


if __name__ == "__main__":
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    file_handler = logging.FileHandler('scheduler.log')
    file_handler.setFormatter(log_formatter)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    scheduler = BlockingScheduler(timezone=pytz.utc)
    scheduler.add_job(check_and_run_tasks, 'interval', minutes=1, next_run_time=datetime.now(pytz.utc))

    logger.info("Scheduler service started. Press Ctrl+C to exit.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler service stopped.")
