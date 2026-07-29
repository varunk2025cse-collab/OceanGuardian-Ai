"""Quick verification that all new modules import correctly."""
import sys
sys.path.insert(0, '.')

from app.main import app
from app.services.boat_readiness_service import BoatReadinessService, ReadinessEvaluation, ReadinessCheck
from app.services.boat_document_service import BoatDocumentService
from app.services.boat_crew_service import BoatCrewService
from app.routers.v2.boats import router as boats_v2_router

print(f"Total routes registered: {len(app.routes)}")
v2_boat_paths = [r.path for r in app.routes if 'v2/boats' in r.path]
print(f"V2 Boat routes ({len(v2_boat_paths)}):")
for p in sorted(v2_boat_paths):
    print(f"  {p}")
print("\nAll imports successful!")
