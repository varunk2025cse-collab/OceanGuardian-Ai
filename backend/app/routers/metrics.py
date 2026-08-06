from fastapi import APIRouter, Response
from app.observability import metrics_response

router = APIRouter()


@router.get("/metrics")
def metrics():
    data, content_type = metrics_response()
    return Response(content=data, media_type=content_type)
