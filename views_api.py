from http import HTTPStatus
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from lnbits.core.crud import get_user
from lnbits.core.models import WalletTypeInfo
from lnbits.core.services import check_transaction_status, create_invoice
from lnbits.decorators import require_admin_key, require_invoice_key
from loguru import logger

from .cloudflare import cloudflare_create_record
from .crud import (
    check_address_available,
    create_address,
    create_domain,
    delete_address,
    delete_domain,
    get_address,
    get_address_by_username,
    get_addresses,
    get_domain,
    get_domains,
    update_domain,
)
from .models import Address, CreateAddress, CreateDomain, Domain

lnaddress_api_router = APIRouter()


@lnaddress_api_router.get("/api/v1/domains")
async def api_domains(
    g: WalletTypeInfo = Depends(require_invoice_key), all_wallets: bool = Query(False)
) -> list[Domain]:
    wallet_ids = [g.wallet.id]
    if all_wallets:
        user = await get_user(g.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    return await get_domains(wallet_ids)


@lnaddress_api_router.post("/api/v1/domains")
@lnaddress_api_router.put("/api/v1/domains/{domain_id}")
async def api_domain_create(
    request: Request,
    data: CreateDomain,
    domain_id=None,
    g: WalletTypeInfo = Depends(require_admin_key),
) -> Domain:
    if domain_id:
        domain = await get_domain(domain_id)

        if not domain:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Domain does not exist."
            )

        if domain.wallet != g.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail="Not your domain"
            )

        domain = await update_domain(domain_id, **data.dict())
    else:

        domain = await create_domain(data=data)
        root_url = urlparse(str(request.url)).netloc

        cf_response = await cloudflare_create_record(domain=domain, ip=root_url)

        if not cf_response or not cf_response["success"]:
            await delete_domain(domain.id)
            err_msg = cf_response["errors"][0]["message"]  # type: ignore
            logger.error(f"Cloudflare failed with: {err_msg}")
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail="Problem with cloudflare."
            )

    return domain


@lnaddress_api_router.delete("/api/v1/domains/{domain_id}")
async def api_domain_delete(
    domain_id: str, g: WalletTypeInfo = Depends(require_admin_key)
):
    domain = await get_domain(domain_id)

    if not domain:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Domain does not exist."
        )

    if domain.wallet != g.wallet.id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Not your domain")

    await delete_domain(domain_id)


@lnaddress_api_router.get("/api/v1/addresses")
async def api_addresses(
    g: WalletTypeInfo = Depends(require_invoice_key), all_wallets: bool = Query(False)
) -> list[Address]:
    wallet_ids = [g.wallet.id]
    if all_wallets:
        user = await get_user(g.wallet.user)
        wallet_ids = user.wallet_ids if user else []
    return await get_addresses(wallet_ids)


@lnaddress_api_router.get("/api/v1/address/availabity/{domain_id}/{username}")
async def api_check_available_username(domain_id, username) -> bool:
    used_username = await check_address_available(username, domain_id)
    return used_username


@lnaddress_api_router.get("/api/v1/address/{domain}/{username}/{wallet_key}")
async def api_get_user_info(username, wallet_key, domain) -> Address:
    address = await get_address_by_username(username, domain)

    if not address:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Address does not exist."
        )

    if address.wallet_key != wallet_key:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Incorrect user/wallet information.",
        )

    return address


@lnaddress_api_router.post("/api/v1/address/{domain_id}")
@lnaddress_api_router.put("/api/v1/address/{domain_id}/{user}/{wallet_key}")
async def api_lnaddress_make_address(
    domain_id, data: CreateAddress, user=None, wallet_key=None
):
    domain = await get_domain(domain_id)

    # If the request is coming for the non-existant domain
    if not domain:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="The domain does not exist."
        )

    domain_cost = domain.cost
    sats = data.sats

    ## FAILSAFE FOR CREATING ADDRESSES BY API
    if domain_cost * data.duration != data.sats:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="The amount is not correct. Either 'duration', or 'sats' are wrong.",
        )

    if user:
        address = await get_address_by_username(user, domain.domain)

        if not address:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="The address does not exist."
            )

        if address.wallet_key != wallet_key:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail="Not your address."
            )

        try:
            payment = await create_invoice(
                wallet_id=domain.wallet,
                amount=data.sats,
                memo=(
                    f"Renew {data.username}@{domain.domain} for "
                    f"{sats} sats for {data.duration} more days"
                ),
                extra={
                    "tag": "renew lnaddress",
                    "id": address.id,
                    "duration": data.duration,
                },
            )

        except Exception as exc:
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(exc)
            ) from exc
    else:
        username_free = await check_address_available(data.username, data.domain)
        # If username is already taken
        if not username_free:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Alias/username already taken.",
            )

        ## ALL OK - create an invoice and return it to the user

        try:
            payment = await create_invoice(
                wallet_id=domain.wallet,
                amount=sats,
                memo=(
                    f"LNAddress {data.username}@{domain.domain} for "
                    f"{sats} sats for {data.duration} days"
                ),
                extra={"tag": "lnaddress"},
            )
        except Exception as exc:
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(exc)
            ) from exc

        address = await create_address(
            payment_hash=payment.payment_hash, wallet=domain.wallet, data=data
        )

        if not address:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="LNAddress could not be fetched.",
            )

    return {"payment_hash": payment.payment_hash, "payment_request": payment.bolt11}


@lnaddress_api_router.get("/api/v1/addresses/{payment_hash}")
async def api_address_send_address(payment_hash):
    address = await get_address(payment_hash)
    assert address
    domain = await get_domain(address.domain)
    assert domain
    try:
        status = await check_transaction_status(domain.wallet, payment_hash)
        is_paid = not status.pending
    except Exception as e:
        return {"paid": False, "error": str(e)}

    if is_paid:
        return {"paid": True}

    return {"paid": False}


@lnaddress_api_router.delete("/api/v1/addresses/{address_id}")
async def api_address_delete(
    address_id, key_info: WalletTypeInfo = Depends(require_admin_key)
):
    address = await get_address(address_id)
    if not address:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Address does not exist."
        )
    if address.wallet != key_info.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not your address."
        )

    await delete_address(address_id)
