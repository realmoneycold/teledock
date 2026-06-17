import asyncio
import base64
import hashlib
import json
import os
import re
import struct
import time

import httpx
from dotenv import load_dotenv
from nacl.signing import SigningKey
from tonutils.clients import TonapiClient
from tonutils.contracts.wallet import WalletV5R1

load_dotenv("/opt/teledock/backend/.env")

FRAGMENT_BASE_URL = "https://fragment.com"
UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Mobile Safari/537.36"
)


async def main():
    seed = os.environ["FRAGMENT_WALLET_SEED"]
    mnemonic = seed.strip().split()

    from ton_core import NetworkGlobalID
    ton_client = TonapiClient(NetworkGlobalID.MAINNET, api_key="AH" + "0" * 48)
    wallet, pub_key, priv_key, _ = WalletV5R1.from_mnemonic(
        client=ton_client,
        mnemonic=" ".join(mnemonic),
    )

    raw_address = wallet.address.to_str(is_user_friendly=False)
    workchain, addr_hash_hex = raw_address.split(":")
    print("Wallet address:", raw_address)

    pub_key_bytes = pub_key.as_bytes if isinstance(pub_key.as_bytes, bytes) else pub_key.as_bytes()
    priv_key_bytes = priv_key.as_bytes if isinstance(priv_key.as_bytes, bytes) else priv_key.as_bytes()
    print("Public key:", pub_key_bytes.hex())

    state_init_boc = wallet.state_init.serialize().to_boc()
    state_init_b64 = base64.b64encode(state_init_boc).decode()

    async with httpx.AsyncClient(follow_redirects=True) as session:
        session.cookies.set("stel_dt", "-300", domain="fragment.com")
        session.headers.update({"User-Agent": UA})

        resp = await session.get(FRAGMENT_BASE_URL + "/")
        hash_match = re.search(r"/api\?hash=([a-f0-9]+)", resp.text)
        proof_match = re.search(r'"tonProofPayload":"([^"]+)"', resp.text)

        if not hash_match:
            print("ERROR: No API hash found in page")
            return
        if not proof_match:
            print("ERROR: No tonProofPayload found — Fragment may not require proof now")
            api_hash = hash_match.group(1)
            print("API hash:", api_hash)
        else:
            api_hash = hash_match.group(1)
            ton_proof_payload = proof_match.group(1)
            print("API hash:", api_hash)
            print("TonProof payload:", ton_proof_payload[:30], "...")

            domain = "fragment.com"
            timestamp = int(time.time())
            domain_bytes = domain.encode()
            payload_bytes = ton_proof_payload.encode()

            msg = b"ton-proof-item-v2/"
            msg += struct.pack(">i", int(workchain))
            msg += bytes.fromhex(addr_hash_hex)
            msg += struct.pack("<I", len(domain_bytes))
            msg += domain_bytes
            msg += struct.pack("<Q", timestamp)
            msg += payload_bytes

            msg_hash = hashlib.sha256(msg).digest()
            sign_payload = b"\xff\xff" + b"ton-connect" + msg_hash
            final_hash = hashlib.sha256(sign_payload).digest()

            signing_key = SigningKey(priv_key_bytes[:32])
            signature = signing_key.sign(final_hash).signature
            signature_b64 = base64.b64encode(signature).decode()

            account_data = {
                "address": raw_address,
                "chain": "-239",
                "walletStateInit": state_init_b64,
                "publicKey": pub_key_bytes.hex(),
            }
            device_data = {
                "platform": "android",
                "appName": "Tonkeeper",
                "appVersion": "26.04.3",
                "maxProtocolVersion": 2,
                "features": [
                    "SendTransaction",
                    {"name": "SignData", "types": ["text", "binary", "cell"]},
                    {"name": "SendTransaction", "maxMessages": 255},
                ],
            }
            proof_data = {
                "timestamp": timestamp,
                "domain": {"lengthBytes": len(domain_bytes), "value": domain},
                "payload": ton_proof_payload,
                "signature": signature_b64,
            }

            session.headers.update({
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Origin": FRAGMENT_BASE_URL,
                "Referer": FRAGMENT_BASE_URL + "/",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            })

            auth_resp = await session.post(
                f"{FRAGMENT_BASE_URL}/api?hash={api_hash}",
                data={
                    "account": json.dumps(account_data, separators=(",", ":")),
                    "device": json.dumps(device_data, separators=(",", ":")),
                    "proof": json.dumps(proof_data, separators=(",", ":")),
                    "method": "checkTonProofAuth",
                },
            )
            print("checkTonProofAuth response:", auth_resp.json())
            new_cookies = dict(session.cookies)
            print("\nNew cookies:", list(new_cookies.keys()))
            for k, v in new_cookies.items():
                print(f"  {k} = {str(v)[:80]}")

            # Now test initBuyStarsRequest with new cookies
            print("\n--- Testing initBuyStarsRequest with new cookies ---")
            async with httpx.AsyncClient(cookies=new_cookies) as test_session:
                test_session.headers.update({
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Origin": FRAGMENT_BASE_URL,
                    "Referer": FRAGMENT_BASE_URL + "/stars",
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "User-Agent": UA,
                })
                r = await test_session.post(
                    f"{FRAGMENT_BASE_URL}/api?hash={api_hash}",
                    data={
                        "method": "searchStarsRecipient",
                        "query": "your_telegram_username",
                        "quantity": "",
                    },
                )
                found = r.json().get("found", {}).get("recipient")
                print("Recipient found:", bool(found))
                if found:
                    r2 = await test_session.post(
                        f"{FRAGMENT_BASE_URL}/api?hash={api_hash}",
                        data={
                            "method": "initBuyStarsRequest",
                            "recipient": found,
                            "quantity": "50",
                            "payment_method": "ton",
                        },
                    )
                    print("initBuyStarsRequest:", r2.json())


asyncio.run(main())
