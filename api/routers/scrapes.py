from fastapi import APIRouter, Security, HTTPException
from api.routers.auth import get_current_user
from app.users import User
from app import db_adapter as database
import pandas as pd
from pydantic import BaseModel
from typing import List

router = APIRouter()

class ScrapeData(BaseModel):
    run_id: int
    data: List[dict]

@router.post("/scrapes/save", tags=["Scrapes"])
async def save_scrape_data(scrape_data: ScrapeData, current_user: User = Security(get_current_user, scopes=["write:scrapes"])):
    """
    Saves scrape data to the database.
    """
    try:
        df = pd.DataFrame(scrape_data.data)
        database.save_prices(scrape_data.run_id, df)
        return {"message": "Scrape data saved successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scrape_runs", tags=["Scrapes"])
async def create_scrape_run(mode: str, context: str, current_user: User = Security(get_current_user, scopes=["write:scrapes"])):
    """
    Creates a new scrape run record.
    """
    try:
        run_id = database.create_scrape_run(mode, context)
        return {"run_id": run_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
