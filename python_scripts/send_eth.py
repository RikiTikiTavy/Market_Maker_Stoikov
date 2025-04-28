from web3 import Web3
from dotenv import load_dotenv
import os

load_dotenv()

MM_ADDRESS = Web3.to_checksum_address(os.getenv("MM_ADDRESS"))
HASHFLOW_ADDRESS = Web3.to_checksum_address(os.getenv("HASHFLOW_ADDRESS"))
MM_PRIVATE_KEY = os.getenv("MM_PRIVATE_KEY")
CHAIN_ID = os.getenv("CHAIN_ID")

ANVIL_URL = os.getenv("ANVIL_URL")
w3 = Web3(Web3.HTTPProvider(ANVIL_URL))

"""
 Посылаем эфиры контракту, потому что он учавствует в цепочке, 
 когда нужно отправить эфир трейдеру
"""
tx = {
    'from': MM_ADDRESS,
    'to': HASHFLOW_ADDRESS,
    'value': w3.to_wei(70, 'ether'),
    'gas': 50000,
    'gasPrice': w3.to_wei('1', 'gwei'),
    'nonce': w3.eth.get_transaction_count(MM_ADDRESS),
    'chainId': CHAIN_ID
}
signed_tx = w3.eth.account.sign_transaction(tx, MM_PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
print("Tx sent:", tx_hash.hex())

