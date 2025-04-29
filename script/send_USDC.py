from web3 import Web3
from dotenv import load_dotenv
import os
import json

load_dotenv()

MM_ADDRESS = Web3.toChecksumAddress(os.getenv("MM_ADDRESS"))
TRADER_ADDRESS = Web3.toChecksumAddress(os.getenv("TRADER_ADDRESS"))
MM_PRIVATE_KEY = os.getenv("MM_PRIVATE_KEY")
CHAIN_ID = int(os.getenv("CHAIN_ID"))
USDC_ADDRESS = Web3.toChecksumAddress(os.getenv("USDC_ADDRESS"))

ANVIL_URL = os.getenv("ANVIL_URL")
w3 = Web3(Web3.HTTPProvider(ANVIL_URL))

def load_abi(path):
    with open(path, "r") as f:
        artifact = json.load(f)
    return artifact["abi"]

USDC_ABI = load_abi("../out/USDCMock.sol/USDCMock.json")
USDC_CONTRACT = w3.eth.contract(address=USDC_ADDRESS, abi=USDC_ABI)

"""
 Посылаем USDC трейдеру
"""

amount_raw = int(500_000 * 10**6)
nonce = w3.eth.get_transaction_count(MM_ADDRESS)

tx = USDC_CONTRACT.functions.transfer(TRADER_ADDRESS, amount_raw).build_transaction({
    'from': MM_ADDRESS,
    'nonce': nonce,
    'gas': 100_000,
    'gasPrice': w3.toWei('1', 'gwei'),
    'chainId': int(os.getenv("CHAIN_ID")),
})

signed_tx = w3.eth.account.sign_transaction(tx, MM_PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
print("Tx sent:", tx_hash.hex())

