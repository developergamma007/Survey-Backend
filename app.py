from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock database - Replace with actual database calls
WARDS = [
    {"id": 1, "ward_name_en": "KR Puram", "ward_name_local": "ಕೃ ಪುರ"},
    {"id": 2, "ward_name_en": "Indiranagar", "ward_name_local": "ಇಂದಿರಾನಗರ"},
    {"id": 3, "ward_name_en": "Whitefield", "ward_name_local": "ವೈಟ್‌ಫೀಲ್ಡ"},
]

BOOTHS = [
    {"id": 1, "booth_no": "9", "booth_name_en": "Gvt High School, Devasandra", "booth_name_local": "ದೇವಸಂದ್ರ ಸರ್ಕಾರಿ ಪ್ರೌಢ ಶಾಲೆ", "ward_id": 1},
    {"id": 2, "booth_no": "10", "booth_name_en": "Primary School, Devasandra", "booth_name_local": "ದೇವಸಂದ್ರ ಪ್ರಾಥಮಿಕ ಶಾಲೆ", "ward_id": 1},
    {"id": 3, "booth_no": "1", "booth_name_en": "Community Center, Indiranagar", "booth_name_local": "ಇಂದಿರಾನಗರ ಕಮ್ಯುನಿಟಿ ಸೆಂಟರ್", "ward_id": 2},
]

class WardResponse(BaseModel):
    id: int
    ward_name_en: str
    ward_name_local: str

class BoothResponse(BaseModel):
    id: int
    booth_no: str
    booth_name_en: str
    booth_name_local: str
    ward_id: int

@app.get("/api/hello")
def read_root():
    return {"message": "Hello from the Survey backend!"}

@app.get("/api/wards", response_model=List[WardResponse])
async def get_wards():
    """Get all wards"""
    return WARDS

@app.get("/api/booths", response_model=List[BoothResponse])
async def get_booths(ward_id: Optional[int] = None):
    """Get booths, optionally filtered by ward_id"""
    if ward_id:
        return [b for b in BOOTHS if b["ward_id"] == ward_id]
    return BOOTHS

@app.get("/api/booths/{booth_id}", response_model=BoothResponse)
async def get_booth(booth_id: int):
    """Get a specific booth by id"""
    for booth in BOOTHS:
        if booth["id"] == booth_id:
            return booth
    return {"error": "Booth not found"}

class SurveyResponse(BaseModel):
    assembly: str
    # ...existing fields...

@app.post("/surveys")
async def create_survey(survey: dict):
    """Submit survey data"""
    try:
        # Here you would save to database
        print(f"Survey received: {survey}")
        return {"status": "success", "message": "Survey submitted successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
