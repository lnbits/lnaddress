import asyncio

from fastapi import APIRouter
from loguru import logger

from .crud import db
from .tasks import wait_for_paid_invoices
from .views import lnaddress_generic_router
from .views_api import lnaddress_api_router
from .views_lnurl import lnaddress_lnurl_router

lnaddress_ext: APIRouter = APIRouter(prefix="/lnaddress", tags=["lnaddress"])
lnaddress_ext.include_router(lnaddress_generic_router)
lnaddress_ext.include_router(lnaddress_api_router)
lnaddress_ext.include_router(lnaddress_lnurl_router)

lnaddress_static_files = [
    {
        "path": "/lnaddress/static",
        "name": "lnaddress_static",
    }
]

lnaddress_redirect_paths = [
    {
        "from_path": "/.well-known/lnurlp",
        "redirect_to_path": "/api/v1/well-known",
    }
]

scheduled_tasks: list[asyncio.Task] = []


def lnaddress_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)


def lnaddress_start():
    from lnbits.tasks import create_permanent_unique_task

    task = create_permanent_unique_task("ext_lnaddress", wait_for_paid_invoices)
    scheduled_tasks.append(task)


__all__ = [
    "db",
    "lnaddress_ext",
    "lnaddress_redirect_paths",
    "lnaddress_start",
    "lnaddress_static_files",
    "lnaddress_stop",
]
