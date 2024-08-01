import hashlib
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Query, Request
from lnurl import LnurlErrorResponse
from loguru import logger

from .crud import get_address, get_address_by_username, get_domain

lnaddress_lnurl_router = APIRouter()


async def lnurl_response(username: str, domain: str, request: Request):
    address = await get_address_by_username(username, domain)

    if not address:
        return {"status": "ERROR", "reason": "Address not found."}

    ## CHECK IF USER IS STILL VALID/PAYING
    now = datetime.now().timestamp()
    start = datetime.fromtimestamp(address.time)
    expiration = (start + timedelta(days=address.duration)).timestamp()

    if now > expiration:
        return LnurlErrorResponse(reason="Address has expired.").dict()

    resp = {
        "tag": "payRequest",
        "callback": request.url_for("lnaddress.lnurl_callback", address_id=address.id),
        "metadata": await address.lnurlpay_metadata(domain=domain),
        "commentAllowed": 100,
        "minSendable": 1000,
        "maxSendable": 1000000000,
    }

    logger.debug("RESP", resp)
    return resp


# redirected from /.well-known/lnurlp
@lnaddress_lnurl_router.get("/api/v1/well-known/{username}")
async def lnaddress(username: str, request: Request):
    domain = request.url.netloc
    return await lnurl_response(username, domain, request)


@lnaddress_lnurl_router.get("/lnurl/cb/{address_id}", name="lnaddress.lnurl_callback")
async def lnurl_callback(
    address_id, amount: int = Query(...), comment: str = Query("")
):
    if len(comment) > 100:
        return LnurlErrorResponse(reason="Comment is too long").dict()
    address = await get_address(address_id)
    if not address:
        return LnurlErrorResponse(reason="Address not found").dict()

    amount_received = amount

    domain = await get_domain(address.domain)
    assert domain

    base_url = (
        address.wallet_endpoint[:-1]
        if address.wallet_endpoint.endswith("/")
        else address.wallet_endpoint
    )

    async with httpx.AsyncClient() as client:
        try:
            metadata = await address.lnurlpay_metadata(domain=domain.domain)
            call = await client.post(
                base_url + "/api/v1/payments",
                headers={
                    "X-Api-Key": address.wallet_key,
                    "Content-Type": "application/json",
                },
                json={
                    "out": False,
                    "amount": int(amount_received / 1000),
                    "unhashed_description": metadata.encode("utf-8").hex(),
                    "description_hash": hashlib.sha256(
                        metadata.encode("utf-8")
                    ).hexdigest(),
                    "extra": {
                        "tag": comment
                        or f"Payment to {address.username}@{domain.domain}"
                    },
                },
                timeout=40,
            )

            r = call.json()
        except Exception:
            return LnurlErrorResponse(reason="ERROR")

    # resp = LnurlPayActionResponse(pr=r["payment_request"], routes=[])
    resp = {"pr": r["payment_request"], "routes": []}

    return resp
