from fastapi import APIRouter

from app.api.routes import (
    agent_budgets,
    agent_categories,
    agent_handler_options,
    agent_transactions,
    api_tokens,
    budgets,
    categories,
    dashboard,
    data_jobs,
    login,
    private,
    transactions,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(categories.router)
api_router.include_router(budgets.router)
api_router.include_router(transactions.router)
api_router.include_router(dashboard.router)
api_router.include_router(api_tokens.router)
api_router.include_router(data_jobs.router)
api_router.include_router(agent_transactions.router)
api_router.include_router(agent_handler_options.router)
api_router.include_router(agent_budgets.router)
api_router.include_router(agent_categories.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
