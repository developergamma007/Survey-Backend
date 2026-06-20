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

# 3 minutes of m4a/webm survey audio is typically well below this.
# Keep nginx/proxy `client_max_body_size` at or above this value.
MAX_AUDIO_UPLOAD_BYTES = int(os.getenv("MAX_AUDIO_UPLOAD_BYTES", str(25 * 1024 * 1024)))
