from web3 import Web3
import os
from dotenv import load_dotenv

load_dotenv()

HASHFLOW_ADDRESS = Web3.toChecksumAddress(os.getenv("HASHFLOW_ADDRESS"))

ANVIL_URL = os.getenv("ANVIL_URL")
w3 = Web3(Web3.HTTPProvider(ANVIL_URL))
hashflow_ETH_balance = w3.eth.get_balance(HASHFLOW_ADDRESS)
print(f"ETH balance: {w3.fromWei(hashflow_ETH_balance, 'ether')} ETH")