import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database configuration — set DATABASE_URL in .env (Survey_Production / survey schema)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is required. Example: "
        "postgresql://surveyuser:password@13.233.40.235:5432/surveydb"
    )
