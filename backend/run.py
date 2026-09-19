import os
import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    reload_flag = not settings.is_production
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=reload_flag)
