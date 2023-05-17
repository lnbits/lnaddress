import asyncio

from fastapi import APIRouter
from starlette.staticfiles import StaticFiles
from typing import List

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_lnaddress")

scheduled_tasks: List[asyncio.Task] = []

lnaddress_ext: APIRouter = APIRouter(prefix="/lnaddress", tags=["lnaddress"])

lnaddress_static_files = [
    {
        "path": "/lnaddress/static",
        "app": StaticFiles(directory="lnbits/extensions/lnaddress/static"),
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
    return template_renderer(["lnbits/extensions/lnaddress/templates"])


from .lnurl import *  # noqa: F401,F403
from .tasks import wait_for_paid_invoices
from .views import *  # noqa: F401,F403
from .views_api import *  # noqa: F401,F403


def lnaddress_start():
    loop = asyncio.get_event_loop()
    task = loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
    scheduled_tasks.append(task)
