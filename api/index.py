import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from metaapi_cloud_sdk import MetaStats
from pydantic_settings import BaseSettings

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class Settings(BaseSettings):
    token: str = os.getenv("METAAPI_TOKEN", "")
    account_id: str = os.getenv("METAAPI_ACCOUNT_ID", "")


settings = Settings()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://nexusfuturefund.vercel.app",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

meta_stats = MetaStats(token=settings.token)

cache: Dict[str, Any] = {}
CACHE_EXPIRY = timedelta(seconds=60)


async def get_full_trading_history(
    start_time: Optional[str] = None, end_time: Optional[str] = None
):
    try:
        start_time = start_time or "2025-01-01 00:00:00.000"
        end_time = (
            end_time or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        )

        logging.info(f"Fetching trading history from {start_time} to {end_time}")

        trades = await meta_stats.get_account_trades(
            account_id=settings.account_id,
            start_time=start_time,
            end_time=end_time,
            update_history=True,
        )
        return trades
    except Exception as e:
        logging.error(f"Error fetching trading history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def trading_history(
    start_time: Optional[str] = None, end_time: Optional[str] = None
):
    cache_key = f"{start_time}_{end_time}"
    cache_entry = cache.get(cache_key)

    # Check in-memory cache
    if cache_entry and datetime.now(timezone.utc) - cache_entry["time"] < CACHE_EXPIRY:
        logging.info("Serving from in-memory cache")
        return cache_entry["data"]

    # Fetch new data if cache miss
    result = await get_full_trading_history(start_time, end_time)

    # Store in cache
    cache[cache_key] = {"data": result, "time": datetime.now(timezone.utc)}

    return result
