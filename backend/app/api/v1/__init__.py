from fastapi import APIRouter

from app.api.v1.routers.ai import router as ai_router
from app.api.v1.routers.auth import router as auth_router
from app.api.v1.routers.documents import router as documents_router
from app.api.v1.routers.financial import router as financial_router
from app.api.v1.routers.users import router as users_router

api_v1_router = APIRouter()
api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(financial_router)
api_v1_router.include_router(ai_router)
api_v1_router.include_router(documents_router)

__all__ = ["api_v1_router"]
