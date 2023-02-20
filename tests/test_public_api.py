import pytest
# check GET /.well-known/lnurlp/{username}: wrong username [should fail]
@pytest.mark.asyncio
async def test_lnaddress_wrong_hash(client):
    username = "wrong_name"
    response = await client.get(f"/.well-known/lnurlp/{username}")
    assert response.status_code == 200
    assert response.json()["status"] == "ERROR"
    assert response.json()["reason"] == "Address not found."
