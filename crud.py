from datetime import datetime, timedelta
from typing import List, Optional, Union

from lnbits.db import Database
from lnbits.helpers import urlsafe_short_hash
from loguru import logger

from .models import Address, CreateAddress, CreateDomain, Domain

db = Database("ext_lnaddress")


async def create_domain(data: CreateDomain) -> Domain:
    domain_id = urlsafe_short_hash()
    domain = Domain(id=domain_id, **data.dict())
    await db.insert("lnaddress.domain", domain)
    return domain


async def update_domain(domain: Domain) -> Domain:
    await db.update("lnaddress.domain", domain)
    return domain


async def delete_domain(domain_id: str) -> None:
    await db.execute("DELETE FROM lnaddress.domain WHERE id = :id", {"id": domain_id})


async def get_domain(domain_id: str) -> Optional[Domain]:
    return await db.fetchone(
        "SELECT * FROM lnaddress.domain WHERE id = :id",
        {"id": domain_id},
        Domain,
    )


async def get_domains(wallet_ids: Union[str, List[str]]) -> List[Domain]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]
    q = ",".join([f"'{w}'" for w in wallet_ids])
    return await db.fetchall(
        f"SELECT * FROM lnaddress.domain WHERE wallet IN ({q})", model=Domain
    )


async def create_address(
    payment_hash: str, wallet: str, data: CreateAddress
) -> Address:
    address = Address(
        id=payment_hash,
        wallet=wallet,
        domain=data.domain,
        email=data.email,
        username=data.username,
        wallet_key=data.wallet_key,
        wallet_endpoint=data.wallet_endpoint,
        sats=data.sats,
        duration=data.duration,
        paid=False,
    )
    await db.insert("lnaddress.address", address)

    return address


async def get_address(address_id: str) -> Optional[Address]:
    return await db.fetchone(
        """
        SELECT a.* FROM lnaddress.address AS a INNER JOIN
        lnaddress.domain AS d ON a.id = :id AND a.domain = d.id
        """,
        {"id": address_id},
        Address,
    )


async def get_address_by_username(username: str, domain: str) -> Optional[Address]:
    return await db.fetchone(
        """
        SELECT a.* FROM lnaddress.address AS a INNER JOIN
        lnaddress.domain AS d ON a.username = :username AND d.domain = :domain
        """,
        {"username": username, "domain": domain},
        Address,
    )


async def delete_address(address_id: str) -> None:
    await db.execute("DELETE FROM lnaddress.address WHERE id = :id", {"id": address_id})


async def get_addresses(wallet_ids: Union[str, List[str]]) -> List[Address]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]
    q = ",".join([f"'{w}'" for w in wallet_ids])
    return await db.fetchall(
        f"SELECT * FROM lnaddress.address WHERE wallet IN ({q})", model=Address
    )


async def set_address_paid(payment_hash: str) -> None:
    await db.execute(
        "UPDATE lnaddress.address SET paid = true WHERE id = :id",
        {"id": payment_hash},
    )


async def set_address_renewed(address_id: str, duration: int):
    address = await get_address(address_id)
    assert address

    extend_duration = int(address.duration) + duration
    await db.execute(
        "UPDATE lnaddress.address SET duration = :duration WHERE id = :id",
        {"duration": extend_duration, "id": address_id},
    )
    updated_address = await get_address(address_id)
    assert updated_address, "Renewed address couldn't be retrieved"
    return updated_address


async def check_address_available(username: str, domain: str) -> bool:
    result = await db.execute(
        """
        SELECT COUNT(username) FROM lnaddress.address
        WHERE username = :username AND domain = :domain
        """,
        {"username": username, "domain": domain},
    )
    row = result.mappings().first()
    return row.get("count", 0) == 0


async def purge_addresses(domain_id: str):

    addresses = await db.fetchall(
        "SELECT * FROM lnaddress.address WHERE domain = :domain",
        {"domain": domain_id},
        Address,
    )

    now = datetime.now().timestamp()

    for r in addresses:

        pay_expire = now > r.time.timestamp() + 86400  # if payment wasn't made in 1 day
        expired = (
            now > (r.time + timedelta(days=r.duration + 1)).timestamp()
        )  # give user 1 day to topup is address

        if not r.paid and pay_expire:
            logger.debug("DELETE UNP_PAY_EXP", r.username)
            await delete_address(r.id)

        if r.paid and expired:
            logger.debug("DELETE PAID_EXP", r.username)
            await delete_address(r.id)
