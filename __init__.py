import asyncio

from fastapi import APIRouter
from loguru import logger

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import create_permanent_unique_task

db = Database("ext_lnaddress")

lnaddress_ext: APIRouter = APIRouter(prefix="/lnaddress", tags=["lnaddress"])

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


def lnaddress_renderer():
    return template_renderer(["lnaddress/templates"])


from .lnurl import *  # noqa: F401,F403
from .tasks import wait_for_paid_invoices
from .views import *  # noqa: F401,F403
from .views_api import *  # noqa: F401,F403


scheduled_tasks: list[asyncio.Task] = []

def lnaddress_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)

def lnaddress_start():
    task = create_permanent_unique_task("ext_lnaddress", wait_for_paid_invoices)
    scheduled_tasks.append(task)
