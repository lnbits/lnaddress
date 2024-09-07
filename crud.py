from datetime import datetime, timedelta
from typing import List, Optional, Union

from lnbits.db import Database
from lnbits.helpers import insert_query, update_query, urlsafe_short_hash
from loguru import logger

from .models import Address, CreateAddress, CreateDomain, Domain

db = Database("ext_lnaddress")


async def create_domain(data: CreateDomain) -> Domain:
    domain_id = urlsafe_short_hash()
    domain = Domain(id=domain_id, **data.dict())
    await db.execute(
        insert_query("lnaddress.domain", domain),
        domain.dict(),
    )
    return domain


async def update_domain(domain: Domain) -> Domain:
    await db.execute(
        update_query("lnaddress.domain", domain),
        domain.dict(),
    )
    return domain


async def delete_domain(domain_id: str) -> None:
    await db.execute("DELETE FROM lnaddress.domain WHERE id = :id", {"id": domain_id})


async def get_domain(domain_id: str) -> Optional[Domain]:
    row = await db.fetchone(
        "SELECT * FROM lnaddress.domain WHERE id = :id", {"id": domain_id}
    )
    return Domain(**row) if row else None


async def get_domains(wallet_ids: Union[str, List[str]]) -> List[Domain]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join([f"'{w}'" for w in wallet_ids])
    rows = await db.fetchall(f"SELECT * FROM lnaddress.domain WHERE wallet IN ({q})")

    return [Domain(**row) for row in rows]


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
        time=int(datetime.now().timestamp()),
    )
    await db.execute(
        insert_query("lnaddress.address", address),
        address.dict(),
    )
    return address


async def get_address(address_id: str) -> Optional[Address]:
    row = await db.fetchone(
        """
        SELECT a.* FROM lnaddress.address AS a INNER JOIN
        lnaddress.domain AS d ON a.id = :id AND a.domain = d.id
        """,
        {"id": address_id},
    )
    return Address(**row) if row else None


async def get_address_by_username(username: str, domain: str) -> Optional[Address]:
    row = await db.fetchone(
        """
        SELECT a.* FROM lnaddress.address AS a INNER JOIN
        lnaddress.domain AS d ON a.username = :username AND d.domain = :domain
        """,
        {"username": username, "domain": domain},
    )

    return Address(**row) if row else None


async def delete_address(address_id: str) -> None:
    await db.execute("DELETE FROM lnaddress.address WHERE id = :id", {"id": address_id})


async def get_addresses(wallet_ids: Union[str, List[str]]) -> List[Address]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join([f"'{w}'" for w in wallet_ids])
    rows = await db.fetchall(f"SELECT * FROM lnaddress.address WHERE wallet IN ({q})")
    return [Address(**row) for row in rows]


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


async def check_address_available(username: str, domain: str):
    row = await db.fetchone(
        """
        SELECT COUNT(username) FROM lnaddress.address
        WHERE username = :username AND domain = :domain
        """,
        {"username": username, "domain": domain},
    )
    return row


async def purge_addresses(domain_id: str):

    rows = await db.fetchall(
        "SELECT * FROM lnaddress.address WHERE domain = :domain", {"domain": domain_id}
    )

    now = datetime.now().timestamp()

    for row in rows:
        r = Address(**row).dict()

        start = datetime.fromtimestamp(r["time"])
        paid = r["paid"]
        pay_expire = now > start.timestamp() + 86400  # if payment wasn't made in 1 day
        expired = (
            now > (start + timedelta(days=r["duration"] + 1)).timestamp()
        )  # give user 1 day to topup is address

        if not paid and pay_expire:
            logger.debug("DELETE UNP_PAY_EXP", r["username"])
            await delete_address(r["id"])

        if paid and expired:
            logger.debug("DELETE PAID_EXP", r["username"])
            await delete_address(r["id"])
