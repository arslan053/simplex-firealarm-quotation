from __future__ import annotations

import httpx

from app.config import settings


class MoyasarClient:
    def __init__(self, secret_key: str | None = None):
        self.secret_key = secret_key or settings.MOYASAR_SECRET_KEY
        self.base_url = "https://api.moyasar.com/v1"

    def _auth(self) -> tuple[str, str]:
        return (self.secret_key, "")

    async def fetch_payment(self, payment_id: str) -> dict:
        """GET /v1/payments/{id} — verify payment status."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/payments/{payment_id}",
                auth=self._auth(),
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def charge_token(
        self,
        token: str,
        amount: int,
        currency: str,
        description: str,
        callback_url: str,
        metadata: dict,
    ) -> dict:
        """POST /v1/payments — charge saved card for auto-renewal."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/payments",
                auth=self._auth(),
                json={
                    "amount": amount,
                    "currency": currency,
                    "description": description,
                    "callback_url": callback_url,
                    "source": {
                        "type": "token",
                        "token": token,
                    },
                    "metadata": metadata,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def fetch_token(self, token_id: str) -> dict:
        """GET /v1/tokens/{id} — get card info."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/tokens/{token_id}",
                auth=self._auth(),
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def refund_payment(self, payment_id: str, amount: int | None = None) -> dict:
        """POST /v1/payments/{id}/refund — full or partial refund."""
        async with httpx.AsyncClient() as client:
            body: dict = {}
            if amount is not None:
                body["amount"] = amount
            resp = await client.post(
                f"{self.base_url}/payments/{payment_id}/refund",
                auth=self._auth(),
                json=body if body else None,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def delete_token(self, token_id: str) -> None:
        """DELETE /v1/tokens/{id} — revoke saved card on Moyasar side."""
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self.base_url}/tokens/{token_id}",
                auth=self._auth(),
                timeout=30.0,
            )
            # 404 is fine — token may already be gone
            if resp.status_code != 404:
                resp.raise_for_status()
