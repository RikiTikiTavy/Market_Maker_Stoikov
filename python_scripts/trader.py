import asyncio
import aiohttp
import random
import time
import os
from web3 import Web3
import json
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

# Загружаем ABI из compiled Forge output
def load_abi(path):
    with open(path, "r") as f:
        artifact = json.load(f)
    return artifact["abi"]

USDC_ABI = load_abi("../out/USDCMock.sol/USDCMock.json")
HASHFLOW_ABI = load_abi("../out/HashflowMock.sol/HashflowMock.json")

ETH_ADDRESS = Web3.toChecksumAddress(os.getenv("ETH_ADDRESS"))
USDC_ADDRESS = Web3.toChecksumAddress(os.getenv("USDC_ADDRESS"))
TRADER_ADDRESS = Web3.toChecksumAddress(os.getenv("TRADER_ADDRESS"))
TRADER_PRIVATE_KEY = os.getenv("TRADER_PRIVATE_KEY")
CHAIN_ID = os.getenv("CHAIN_ID")
QUOTE_ENDPOINT = "http://localhost:8000/quote"


ANVIL_URL = os.getenv("ANVIL_URL")
w3 = Web3(Web3.HTTPProvider(ANVIL_URL))

HASHFLOW_ADDRESS = Web3.toChecksumAddress(os.getenv("HASHFLOW_ADDRESS"))
HASHFLOW_CONTRACT = w3.eth.contract(address=HASHFLOW_ADDRESS, abi=HASHFLOW_ABI)


def execute_trade(quote: dict, is_selling_eth: bool):

    eth_value = int(quote["baseAmount"] * 1e18) if is_selling_eth else 0

    quote_struct = (
        int(quote["baseAmount"] * 1e18),
        int(quote["quoteAmount"] * 1e6),
        int(quote["price"] * 1e6),
        int(quote["expiry"]),
        Web3.toChecksumAddress(quote["maker"]),
        TRADER_ADDRESS,
        bytes.fromhex(quote["signature"][2:])
    )

    tx = HASHFLOW_CONTRACT.functions.trade(quote_struct, is_selling_eth).build_transaction({
        'from': TRADER_ADDRESS,
        'value': eth_value,
        'nonce': w3.eth.get_transaction_count(TRADER_ADDRESS),
        'gas': 200_000,
        'gasPrice': w3.toWei('1', 'gwei')
    })

    signed_tx = w3.eth.account.sign_transaction(tx, TRADER_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(f"Trade submitted: {tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Trade confirmed in block {receipt.blockNumber}")

async def send_rfq(session, is_selling_eth: bool):

    TRADER_MODE = random.choice(["aggressive", "conservative"])

    multiplier = 2.0 if TRADER_MODE == "aggressive" else 1

    if is_selling_eth:
        base_token = ETH_ADDRESS
        quote_token = USDC_ADDRESS
        base_amount = round(random.uniform(1.5, 2.0), 4) * multiplier  # ETH
    else:
        base_token = USDC_ADDRESS
        quote_token = ETH_ADDRESS
        base_amount = round(random.uniform(2000, 3000), 2) * multiplier  # USDC

    rfq = {
        "baseToken": base_token,
        "quoteToken": quote_token,
        "baseAmount": base_amount,
        "trader": TRADER_ADDRESS,
        "chainId": CHAIN_ID,
        "TRADER_MODE": TRADER_MODE
    }

    print("=== RFQ ===")
    print(rfq)
    print("==============================")

    async with session.post(QUOTE_ENDPOINT, json=rfq) as response:

        quote = await response.json()

        print("=== RESPONSE FROM MM ===")
        print("QUOTE RESPONSE:", quote)
        print("==============================")

        execute_trade(quote, is_selling_eth)

def approve_usdc(amount: float):
    amount_raw = int(amount * 1e6)
    nonce = w3.eth.get_transaction_count(TRADER_ADDRESS)
    USDC_CONTRACT = w3.eth.contract(address=USDC_ADDRESS, abi=USDC_ABI)

    tx = USDC_CONTRACT.functions.approve(HASHFLOW_ADDRESS, amount_raw).build_transaction({
        'from': TRADER_ADDRESS,
        'nonce': nonce,
        'gas': 100_000,
        'gasPrice': w3.toWei('1', 'gwei')
    })

    signed_tx = w3.eth.account.sign_transaction(tx, TRADER_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Approve confirmed block {receipt.blockNumber}")

async def main():
    async with aiohttp.ClientSession() as session:
        while True:
            is_selling_eth=random.choice([True, False])
            await send_rfq(session, is_selling_eth)
            await asyncio.sleep(10)

if __name__ == "__main__":

    approve_usdc(amount=1_000_000)

    USDC_CONTRACT = w3.eth.contract(address=USDC_ADDRESS, abi=USDC_ABI)
    allowance = USDC_CONTRACT.functions.allowance(TRADER_ADDRESS, HASHFLOW_ADDRESS).call()
    print(f"USDC allowance: {allowance / 1e6}")

    asyncio.run(main())
