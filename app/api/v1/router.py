"""API v1 router — includes all sub-routers."""

from fastapi import APIRouter

from . import auth, users, products, purchase_orders, transactions, stats

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(products.router)
api_router.include_router(purchase_orders.router)
api_router.include_router(transactions.router)
api_router.include_router(stats.router)
