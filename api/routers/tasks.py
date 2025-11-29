from fastapi import APIRouter, Security
from api.routers.auth import get_current_user
from app.users import User
import glob
import os
import json
from app.config import SCHEDULED_TASKS_DIR

router = APIRouter()

@router.get("/tasks", tags=["Tasks"])
async def get_scheduled_tasks(current_user: User = Security(get_current_user, scopes=["read:tasks"])):
    """
    Renders a list of existing scheduled tasks with their status and controls.
    """
    tasks_dir = SCHEDULED_TASKS_DIR
    if not os.path.exists(tasks_dir) or not os.listdir(tasks_dir):
        return []

    task_files = sorted(glob.glob(os.path.join(tasks_dir, '*.json')))
    tasks = []
    for task_file in task_files:
        try:
            with open(task_file, 'r') as f:
                task_config = json.load(f)
                tasks.append(task_config)
        except Exception as e:
            print(f"Error loading task file {os.path.basename(task_file)}: {e}")
    
    return tasks
