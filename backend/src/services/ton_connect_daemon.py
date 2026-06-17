"""
TonConnect v2 Bridge Daemon
============================
Maintains a persistent wallet connection to Fragment.com via the TonConnect v2
bridge protocol. This keeps the stel_ton_token session active so that
initBuyStarsRequest / initBuyPremiumRequest succeed without "Access denied".

Architecture:
- Runs as a background service alongside the fulfillment worker
- Connects to walletbot.me/tonconnect-bridge/bridge as a Tonkeeper-like wallet
- Handles sendTransaction by signing with the wallet seed and broadcasting to TON
- Auto-reconnects on disconnect
- Saves session state to disk so restarts are seamless

Setup (one-time):
    python scripts/run_ton_connect_setup.py
This opens Fragment.com via headless browser, clicks "Connect TON",
intercepts the TonConnect URL, and completes the wallet handshake.

Run:
    python scripts/run_ton_connect_daemon.py
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import struct
import sys
import time
from pathlib import Path
from typing import Optional

import httpx
from nacl.public import Box, PrivateKey, PublicKey
from nacl.signing import SigningKey

sys.path.insert(0, "/opt/teledock/backend")
from dotenv import load_dotenv
load_dotenv("/opt/teledock/backend/.env")

logger = logging.getLogger(__name__)

BRIDGE_HOST = "https://bridge.tonapi.io"
BRIDGE_SSE_URL  = f"{BRIDGE_HOST}/bridge/events"
BRIDGE_POST_URL = f"{BRIDGE_HOST}/bridge/message"
STATE_PATH = Path("/opt/teledock/backend/.ton_connect_state.json")
CONNECT_TIMEOUT = 60.0   # seconds to wait for Fragment to send connect request
RECONNECT_DELAY = 5.0


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------
def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            pass
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


# ---------------------------------------------------------------------------
# TonConnect wallet helpers
# ---------------------------------------------------------------------------
def init_wallet(seed: str):
    """Return (wallet, pub_key_bytes, priv_key_bytes, raw_address, state_init_b64)."""
    from ton_core import NetworkGlobalID
    from tonutils.clients import TonapiClient
    from tonutils.contracts.wallet import WalletV5R1

    ton_client = TonapiClient(NetworkGlobalID.MAINNET, api_key="AH" + "0" * 48)
    wallet, pub_key, priv_key, _ = WalletV5R1.from_mnemonic(
        client=ton_client,
        mnemonic=seed.strip(),
    )
    pub_bytes = pub_key.as_bytes if isinstance(pub_key.as_bytes, bytes) else bytes(pub_key)
    priv_bytes = priv_key.as_bytes if isinstance(priv_key.as_bytes, bytes) else bytes(priv_key)
    raw_address = wallet.address.to_str(is_user_friendly=False)
    state_init_b64 = base64.b64encode(
        wallet.state_init.serialize().to_boc()
    ).decode()
    return wallet, pub_bytes, priv_bytes, raw_address, state_init_b64


def make_ton_proof(
    priv_key_bytes: bytes,
    workchain: str,
    addr_hash_hex: str,
    payload: str,
) -> dict:
    """Build the TonProof structure signed with the wallet key."""
    domain = "fragment.com"
    timestamp = int(time.time())
    domain_bytes = domain.encode()

    msg = b"ton-proof-item-v2/"
    msg += struct.pack(">i", int(workchain))
    msg += bytes.fromhex(addr_hash_hex)
    msg += struct.pack("<I", len(domain_bytes))
    msg += domain_bytes
    msg += struct.pack("<Q", timestamp)
    msg += payload.encode()

    msg_hash = hashlib.sha256(msg).digest()
    sign_payload = b"\xff\xff" + b"ton-connect" + msg_hash
    final_hash = hashlib.sha256(sign_payload).digest()

    signature = SigningKey(priv_key_bytes[:32]).sign(final_hash).signature

    return {
        "timestamp": timestamp,
        "domain": {"lengthBytes": len(domain_bytes), "value": domain},
        "payload": payload,
        "signature": base64.b64encode(signature).decode(),
    }


# ---------------------------------------------------------------------------
# Bridge communication
# ---------------------------------------------------------------------------
def encrypt_message(
    session_privkey: PrivateKey,
    recipient_client_id: str,
    message: dict,
) -> str:
    """Encrypt a message for the recipient using NaCl box."""
    recipient_pubkey = PublicKey(bytes.fromhex(recipient_client_id))
    box = Box(session_privkey, recipient_pubkey)
    plaintext = json.dumps(message).encode()
    encrypted = box.encrypt(plaintext)   # returns nonce(24) + ciphertext
    return base64.b64encode(bytes(encrypted)).decode()


def decrypt_message(
    session_privkey: PrivateKey,
    sender_client_id: str,
    data_b64: str,
) -> dict:
    """Decrypt a message from the sender using NaCl box."""
    sender_pubkey = PublicKey(bytes.fromhex(sender_client_id))
    box = Box(session_privkey, sender_pubkey)
    data = base64.b64decode(data_b64)
    plaintext = box.decrypt(data)
    return json.loads(plaintext)


async def send_bridge_message(
    wallet_client_id: str,
    to_client_id: str,
    payload_b64: str,
    topic: Optional[str] = None,
) -> int:
    """POST a message to the TonConnect bridge. Returns HTTP status code."""
    params = {
        "client_id": wallet_client_id,
        "to": to_client_id,
        "ttl": "300",
    }
    if topic:
        params["topic"] = topic
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            BRIDGE_POST_URL,
            params=params,
            content=payload_b64,
            headers={"Content-Type": "text/plain"},
        )
        return resp.status_code


# ---------------------------------------------------------------------------
# TON transaction signing
# ---------------------------------------------------------------------------
async def sign_and_broadcast_transaction(seed: str, tx_data: dict) -> Optional[str]:
    """Sign a TON transaction using the wallet seed and broadcast it. Returns BOC hex."""
    try:
        from FragmentAPI import FragmentClient
        from FragmentAPI.utils.wallet import execute_transaction, build_account_info

        settings_env = {
            "seed": seed,
            "cookies": {
                "stel_ssid": os.environ.get("FRAGMENT_COOKIE_STEL_SSID", ""),
                "stel_dt": os.environ.get("FRAGMENT_COOKIE_STEL_DT", "-300"),
                "stel_token": os.environ.get("FRAGMENT_COOKIE_STEL_TOKEN", ""),
                "stel_ton_token": os.environ.get("FRAGMENT_COOKIE_STEL_TON_TOKEN", ""),
            },
        }

        client = FragmentClient(
            seed=seed,
            cookies=settings_env["cookies"],
            wallet_version="V5R1",
        )

        result = await execute_transaction(client, tx_data)
        logger.info("Transaction broadcast: tx_hash=%s", result.tx_hash)
        return result.boc
    except Exception as exc:
        logger.error("Transaction signing/broadcast failed: %s", exc, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Core Daemon
# ---------------------------------------------------------------------------
class TonConnectDaemon:
    def __init__(self):
        self.seed = os.environ["FRAGMENT_WALLET_SEED"]
        state = load_state()

        # Session key pair (X25519) for bridge encryption
        if "session_privkey_hex" in state:
            privkey_bytes = bytes.fromhex(state["session_privkey_hex"])
            self.session_privkey = PrivateKey(privkey_bytes)
        else:
            self.session_privkey = PrivateKey.generate()
            state["session_privkey_hex"] = bytes(self.session_privkey).hex()
            save_state(state)

        self.session_pubkey = self.session_privkey.public_key
        self.wallet_client_id = bytes(self.session_pubkey).hex()

        self.dapp_client_id: Optional[str] = state.get("dapp_client_id")
        self.last_event_id: int = state.get("last_event_id", 0)

        # Initialize TON wallet
        (
            self.wallet,
            self.pub_key_bytes,
            self.priv_key_bytes,
            self.raw_address,
            self.state_init_b64,
        ) = init_wallet(self.seed)
        workchain, self.addr_hash_hex = self.raw_address.split(":")
        self.workchain = workchain

        logger.info(
            "TonConnect Daemon initialized | wallet_client_id=%s...  TON addr=%s",
            self.wallet_client_id[:16],
            self.wallet.address.to_str(is_user_friendly=True),
        )

    # -----------------------------------------------------------------------
    # Connection setup
    # -----------------------------------------------------------------------
    def parse_tc_url(self, tc_url: str) -> tuple[str, dict]:
        """Parse a TonConnect URL and return (dapp_client_id, connect_request)."""
        import urllib.parse

        parsed = urllib.parse.urlparse(tc_url)
        params = urllib.parse.parse_qs(parsed.query)

        dapp_id = params.get("id", [None])[0]
        r_raw = params.get("r", [None])[0]

        if not dapp_id or not r_raw:
            raise ValueError(f"Missing id or r in TonConnect URL: {tc_url}")

        # r can be either URL-encoded JSON or base64url-encoded JSON
        # Try URL-decoded JSON first (most common in newer TonConnect URLs)
        r_decoded = urllib.parse.unquote(r_raw)
        try:
            connect_request = json.loads(r_decoded)
            return dapp_id, connect_request
        except json.JSONDecodeError:
            pass

        # Fall back: try base64url decoding
        try:
            padding = 4 - len(r_raw) % 4
            if padding != 4:
                r_raw += "=" * padding
            r_bytes = base64.urlsafe_b64decode(r_raw)
            connect_request = json.loads(r_bytes)
            return dapp_id, connect_request
        except Exception:
            pass

        raise ValueError(f"Could not parse r parameter in TonConnect URL")

    async def complete_handshake(self, dapp_client_id: str, connect_request: dict) -> bool:
        """Send ConnectEvent to Fragment to complete TonConnect handshake."""
        proof_payload = None
        for item in connect_request.get("items", []):
            if item.get("name") == "ton_proof":
                proof_payload = item.get("payload")
                break

        items = [
            {
                "name": "ton_addr",
                "address": self.raw_address,
                "network": "-239",
                "publicKey": self.pub_key_bytes.hex(),
                "walletStateInit": self.state_init_b64,
            }
        ]

        if proof_payload:
            proof = make_ton_proof(
                self.priv_key_bytes,
                self.workchain,
                self.addr_hash_hex,
                proof_payload,
            )
            items.append({"name": "ton_proof", "proof": proof})

        connect_event = {
            "event": "connect",
            "id": int(time.time() * 1000),
            "payload": {
                "device": {
                    "platform": "android",
                    "appName": "Tonkeeper",
                    "appVersion": "26.04.3",
                    "maxProtocolVersion": 2,
                    "features": [
                        "SendTransaction",
                        {"name": "SignData", "types": ["text", "binary", "cell"]},
                        {"name": "SendTransaction", "maxMessages": 255},
                    ],
                },
                "items": items,
            },
        }

        payload_b64 = encrypt_message(self.session_privkey, dapp_client_id, connect_event)
        status = await send_bridge_message(self.wallet_client_id, dapp_client_id, payload_b64)

        if status == 200:
            self.dapp_client_id = dapp_client_id
            state = load_state()
            state["dapp_client_id"] = dapp_client_id
            state["last_event_id"] = self.last_event_id
            save_state(state)
            logger.info("TonConnect handshake complete! dapp_client_id=%s...", dapp_client_id[:16])
            return True
        else:
            logger.error("Bridge returned HTTP %s during handshake", status)
            return False

    async def wait_for_connect_request(self, timeout: float = CONNECT_TIMEOUT) -> Optional[dict]:
        """
        Listen on the bridge for a ConnectRequest from Fragment.
        Fragment sends this when the user clicks 'Connect TON' and selects our wallet.
        Returns the message dict or None on timeout.
        """
        url = (
            f"{BRIDGE_SSE_URL}"
            f"?client_id={self.wallet_client_id}"
            f"&last_event_id={self.last_event_id}"
        )
        logger.info("Waiting for ConnectRequest on bridge (timeout=%ss)...", timeout)

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("GET", url) as response:
                    deadline = time.time() + timeout
                    async for line in response.aiter_lines():
                        if time.time() > deadline:
                            return None
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if not data_str:
                                continue
                            # ConnectRequest is sent unencrypted (wallet doesn't know dApp key yet)
                            try:
                                msg = json.loads(base64.b64decode(data_str))
                                if msg.get("method") == "connect" or "manifestUrl" in str(msg):
                                    return msg
                                # Try as raw JSON
                                return msg
                            except Exception:
                                # Try treating as hex-encoded key exchange
                                pass
        except asyncio.TimeoutError:
            pass
        return None

    # -----------------------------------------------------------------------
    # Ongoing bridge listener
    # -----------------------------------------------------------------------
    async def handle_message(self, msg: dict):
        """Process an incoming bridge message."""
        method = msg.get("method")
        msg_id = msg.get("id")

        if method == "sendTransaction":
            params = msg.get("params", [])
            if not params:
                return
            tx_data_str = params[0] if isinstance(params[0], str) else json.dumps(params[0])
            tx_data = json.loads(tx_data_str)
            logger.info(
                "sendTransaction received: valid_until=%s messages=%d",
                tx_data.get("valid_until"),
                len(tx_data.get("messages", [])),
            )

            boc = await sign_and_broadcast_transaction(self.seed, tx_data)
            if boc:
                response = {"id": msg_id, "result": json.dumps({"boc": boc})}
            else:
                response = {"id": msg_id, "error": {"code": 0, "message": "Signing failed"}}

            payload_b64 = encrypt_message(self.session_privkey, self.dapp_client_id, response)
            await send_bridge_message(
                self.wallet_client_id, self.dapp_client_id, payload_b64
            )

        elif method == "signData":
            logger.info("signData request received (id=%s)", msg_id)
            error_response = {"id": msg_id, "error": {"code": 400, "message": "Not supported"}}
            payload_b64 = encrypt_message(self.session_privkey, self.dapp_client_id, error_response)
            await send_bridge_message(self.wallet_client_id, self.dapp_client_id, payload_b64)

        else:
            logger.debug("Unknown bridge method: %s", method)

    async def listen_forever(self):
        """Persistent bridge listener. Reconnects automatically."""
        if not self.dapp_client_id:
            logger.warning("No dapp_client_id set — run setup first!")
            return

        while True:
            try:
                url = (
                    f"{BRIDGE_SSE_URL}"
                    f"?client_id={self.wallet_client_id}"
                    f"&last_event_id={self.last_event_id}"
                )
                logger.info(
                    "Bridge listener connected (client=%s..., dapp=%s...)",
                    self.wallet_client_id[:12],
                    self.dapp_client_id[:12],
                )

                async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=30)) as client:
                    async with client.stream("GET", url) as response:
                        async for line in response.aiter_lines():
                            line = line.strip()
                            if not line:
                                continue

                            if line.startswith("id:"):
                                try:
                                    self.last_event_id = int(line[3:].strip())
                                    state = load_state()
                                    state["last_event_id"] = self.last_event_id
                                    save_state(state)
                                except ValueError:
                                    pass

                            elif line.startswith("data:"):
                                data_str = line[5:].strip()
                                if not data_str:
                                    continue
                                try:
                                    msg = decrypt_message(
                                        self.session_privkey,
                                        self.dapp_client_id,
                                        data_str,
                                    )
                                    asyncio.create_task(self.handle_message(msg))
                                except Exception as exc:
                                    logger.debug("Decrypt failed: %s", exc)

            except (httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                logger.warning("Bridge disconnected: %s — reconnecting in %ss", exc, RECONNECT_DELAY)
                await asyncio.sleep(RECONNECT_DELAY)
            except Exception as exc:
                logger.error("Bridge error: %s — reconnecting in %ss", exc, RECONNECT_DELAY)
                await asyncio.sleep(RECONNECT_DELAY)


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------
async def run_daemon():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    daemon = TonConnectDaemon()
    await daemon.listen_forever()


if __name__ == "__main__":
    asyncio.run(run_daemon())
