from typing import Any, Dict
import io
import sys
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse, Response

# Ensure the app package is importable when running from repo root
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.schemas import SelectionAnalysisRequest, ShowtimeViewRequest

from app.utils import (
    generate_selection_analysis_report,
    to_csv,
    generate_showtime_html_report,
    generate_showtime_pdf_report,
)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.post("/selection-analysis")
def selection_analysis(req: SelectionAnalysisRequest, format: str = Query("csv", regex="^(csv|json)$")):
    df = generate_selection_analysis_report(req.selected_showtimes)
    if format == "json":
        return JSONResponse(content={"rows": df.to_dict(orient="records") if not df.empty else []})
    # CSV default
    csv_bytes = to_csv(df)
    return StreamingResponse(io.BytesIO(csv_bytes), media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=Showtime_Selection_Analysis.csv"
    })


@router.post("/showtime-view/html")
def showtime_view_html(req: ShowtimeViewRequest):
    html_bytes = generate_showtime_html_report(
        req.all_showings,
        req.selected_films,
        req.theaters,
        (req.date_start, req.date_end),
        cache_data={},
        context_title=req.context_title,
    )
    return Response(content=html_bytes, media_type="text/html")


@router.post("/showtime-view/pdf")
async def showtime_view_pdf(req: ShowtimeViewRequest):
    try:
        pdf_bytes = await generate_showtime_pdf_report(
            req.all_showings,
            req.selected_films,
            req.theaters,
            (req.date_start, req.date_end),
            cache_data={},
            context_title=req.context_title,
        )
        return Response(content=pdf_bytes, media_type="application/pdf", headers={
            "Content-Disposition": "attachment; filename=Showtime_View.pdf"
        })
    except Exception as e:
        # Fallback guidance mirrors UI behavior
        return JSONResponse(status_code=503, content={
            "error": "PDF generation failed. Install Playwright browsers: 'playwright install chromium' in venv.",
            "detail": str(e)
        })
