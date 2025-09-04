import json
from datetime import datetime, timezone

from fastapi import Query
from lnurl.types import LnurlPayMetadata
from pydantic import BaseModel, Field


class CreateDomain(BaseModel):
    wallet: str = Query(...)
    domain: str = Query(...)
    cf_token: str = Query(...)
    cf_zone_id: str = Query(...)
    webhook: str = Query(None)
    cost: int = Query(..., ge=0)


class Domain(BaseModel):
    id: str
    wallet: str
    domain: str
    cf_token: str
    cf_zone_id: str
    webhook: str | None
    cost: int
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreateAddress(BaseModel):
    domain: str = Query(...)
    username: str = Query(...)
    email: str = Query(None)
    wallet_endpoint: str = Query(...)
    wallet_key: str = Query(...)
    sats: int = Query(..., ge=0)
    duration: int = Query(..., ge=1)


class Address(BaseModel):
    id: str
    wallet: str
    domain: str
    email: str | None
    username: str
    wallet_key: str
    wallet_endpoint: str
    sats: int
    duration: int
    paid: bool
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    async def lnurlpay_metadata(self, domain) -> LnurlPayMetadata:
        text = f"Payment to {self.username}"
        identifier = f"{self.username}@{domain}"
        metadata = [["text/plain", text], ["text/identifier", identifier]]

        return LnurlPayMetadata(json.dumps(metadata))
