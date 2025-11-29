from fastapi import APIRouter, Security
from api.routers.auth import get_current_user
from app.users import User
import json
import os
import glob
from app.config import DATA_DIR

router = APIRouter()

@router.get("/markets", tags=["Markets"])
async def get_all_markets(current_user: User = Security(get_current_user, scopes=["read:markets"])):
    """
    Loads and returns all market data from all company directories.
    In a real application, this would be backed by a database.
    """
    markets_data = {}
    for market_file in glob.glob(os.path.join(DATA_DIR, '*', 'markets.json')):
        with open(market_file, 'r') as f:
            try:
                markets_data.update(json.load(f))
            except json.JSONDecodeError:
                print(f"Warning: Could not load or parse {market_file}. Skipping.")
    return markets_data
