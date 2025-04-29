# MVP Market Maker for Hashflow (USD+ / wETH) with EIP-712 signature

import time
import requests
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from eth_account import Account
import os
from dotenv import load_dotenv
from eth_utils import to_checksum_address
from web3 import Web3
import threading
import json
import numpy as np
import time

load_dotenv()

# Загружаем ABI из compiled Forge output
def load_abi(path):
    with open(path, "r") as f:
        artifact = json.load(f)
    return artifact["abi"]

USDC_ABI = load_abi("../out/USDCMock.sol/USDCMock.json")
HASHFLOW_ABI = load_abi("../out/HashflowMock.sol/HashflowMock.json")

ANVIL_URL = os.getenv("ANVIL_URL")
w3 = Web3(Web3.HTTPProvider(ANVIL_URL))

BINANCE_SYMBOL = "ETHUSDT"
MM_PRIVATE_KEY = os.getenv("MM_PRIVATE_KEY")
MM_ADDRESS = Web3.toChecksumAddress(os.getenv("MM_ADDRESS"))
HASHFLOW_ADDRESS = Web3.toChecksumAddress(os.getenv("HASHFLOW_ADDRESS"))
ETH_ADDRESS = Web3.toChecksumAddress(os.getenv("ETH_ADDRESS"))
USDC_ADDRESS = Web3.toChecksumAddress(os.getenv("USDC_ADDRESS"))
CHAIN_ID = int(os.getenv("CHAIN_ID"))

app = FastAPI()


class RFQ(BaseModel):
    baseToken: str
    quoteToken: str
    baseAmount: float
    trader: str
    chainId: int



def compute_volatility():

    interval = 35 # number of candles
    url = f"https://api.binance.us/api/v3/klines?symbol=ETHUSDT&interval=1m&limit={interval}"
    data = requests.get(url).json()
    close_prices = [float(candle[4]) for candle in data]

    log_returns = np.diff(np.log(close_prices))
    vol_minute = np.std(log_returns)
    vol_second = vol_minute / np.sqrt(60)

    return vol_second


def compute_k(volume_eth: float):
    """
    Расчёт k_bid и k_ask на основе заявленного объёма сделки.

    volume_eth — объём в ETH, который трейдер хочет купить/продать
    """
    
    # 1. Скачиваем стакан с Binance
    url = "https://api.binance.us/api/v3/depth?symbol=ETHUSDT&limit=50"
    response = requests.get(url)
    data = response.json()

    bids = [(float(p), float(q)) for p, q in data['bids']]
    asks = [(float(p), float(q)) for p, q in data['asks']]
    mid_price = (bids[0][0] + asks[0][0] )/2

    # 3. Ищем на какую глубину нужно пройти, чтобы набрать нужный объём
    
    cumulative_bid_cost_usd = 0
    cumulative_ask_cost_usd = 0


    total_bid_qty = 0
    for price, qty in bids:
        
        total_bid_qty += qty
        cumulative_bid_cost_usd += (mid_price - price) * qty

        if total_bid_qty >= volume_eth:
            break

    total_ask_qty = 0
    for price, qty in asks:
        total_ask_qty += qty
        cumulative_ask_cost_usd += (price - mid_price) * qty
        if total_ask_qty >= volume_eth:
            break

    k_bid = volume_eth / cumulative_bid_cost_usd
    k_ask = volume_eth / cumulative_ask_cost_usd
    print('k_bid ', k_bid)
    print('k_ask ', k_ask)
    return k_bid, k_ask


# TODO добавить алгоритм через margin вмето k

def get_stoikov_prices(volume_eth: float):
    
    gamma = 0.4 # насколько мы боимся рынка
    k_bid, k_ask = compute_k(volume_eth) # ликвидность


    time_horizon = 3600 # торгуем в течение часа
    
    vol_second = compute_volatility()
    

    start_time = time.time() - 10  # Пример: торговля началась 10 секунд назад

    binance_bid, binance_ask = get_binance_price()
    
    binance_mid_price = (binance_bid + binance_ask) / 2

    eth_balance, usdc_balance = get_balance()

    eth = float(w3.fromWei(eth_balance, 'ether'))
  
    inventory = eth - (usdc_balance / binance_mid_price) # баланс портфеля: ETH минус эквивалент USDC в ETH
    
    t = time.time() - start_time # сколько времени осталось до конца торгов
    T_minus_t = max(1e-9, time_horizon - t) # чтобы не было нуля

    reservation_price = binance_mid_price - inventory * gamma * vol_second**2 * T_minus_t # справедливая цена с учётом позиции и оставшегося времени

    stoikov_bid_price = reservation_price - (gamma * vol_second**2 * T_minus_t + (2 / gamma) * np.log(1 + gamma / k_bid)) / 2
    stoikov_ask_price = reservation_price + (gamma * vol_second**2 * T_minus_t + (2 / gamma) * np.log(1 + gamma / k_ask)) / 2

    print(f"inventory {inventory}")
    print(f"Reservation price: {reservation_price}")
    print(f"Binance bid {binance_bid}, Binance ask {binance_ask}")
    print(f"Stoikov bid {stoikov_bid_price}, Stoikov ask {stoikov_ask_price}")

    return stoikov_bid_price, stoikov_ask_price


def get_binance_price():
    url = f"https://api.binance.us/api/v3/ticker/bookTicker?symbol={BINANCE_SYMBOL}"
    r = requests.get(url)
    data = r.json()
    bid = float(data['bidPrice'])
    ask = float(data['askPrice'])
    return bid, ask



def approve_usdc(amount: float):

    amount_raw = int(amount * 10**6)
    nonce = w3.eth.get_transaction_count(MM_ADDRESS)
    USDC_CONTRACT = w3.eth.contract(address=USDC_ADDRESS, abi=USDC_ABI)
    tx = USDC_CONTRACT.functions.approve(HASHFLOW_ADDRESS, amount_raw).build_transaction({
        'from': MM_ADDRESS,
        'nonce': nonce,
        'gas': 100_000,
        'gasPrice': w3.toWei('1', 'gwei'),
        'chainId': 31337
    })

    signed_tx = w3.eth.account.sign_transaction(tx, MM_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Approve confirmed in block {receipt.blockNumber}")



# Sign quote using EIP-712

from eth_account import Account
from eth_account.messages import encode_structured_data

def sign_quote(message):
    quote_type = [
        {"name": "baseAmount", "type": "uint256"},
        {"name": "quoteAmount", "type": "uint256"},
        {"name": "price", "type": "uint256"},
        {"name": "expiry", "type": "uint256"},
        {"name": "maker", "type": "address"},
        {"name": "trader", "type": "address"}
    ]

    domain = {
        "name": "Hashflow RFQ",
        "version": "1",
        "chainId": CHAIN_ID,
        "verifyingContract": HASHFLOW_ADDRESS
    }

    typed_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Quote": quote_type
        },
        "primaryType": "Quote",
        "domain": domain,
        "message": message
    }

    encoded = encode_structured_data(primitive=typed_data)

    signed = Account.sign_message(encoded, private_key=MM_PRIVATE_KEY)

    return signed.signature.hex()







@app.post("/quote")
async def get_quote(rfq: RFQ):

    
    expiry_ts = int(time.time()) + 60

    is_selling_eth = Web3.toChecksumAddress(rfq.baseToken) == ETH_ADDRESS

    stoikov_bid_price, stoikov_ask_price = get_stoikov_prices(rfq.baseAmount)

    price = stoikov_ask_price if is_selling_eth else stoikov_bid_price
    print("SIDE", "ASK" if is_selling_eth else "BID")

    if is_selling_eth:
        total = rfq.baseAmount * price  # продаёт ETH → умножаем
    else:
        total = rfq.baseAmount / price  # продаёт USDC → делим

    message = {
        "baseAmount": int(rfq.baseAmount * 1e6), 
        "quoteAmount": int(total * 1e6),         
        "price": int(price * 1e6),
        "expiry": expiry_ts,
        "maker": MM_ADDRESS,
        "trader": rfq.trader
    }

    signature = sign_quote(message)

   
    return {
        "price": price,
        "quoteAmount": total,
        "baseAmount": rfq.baseAmount,
        "expiry": expiry_ts,
        "signature": signature,
        "maker": MM_ADDRESS,
        "side": "ask" if is_selling_eth else "bid"
    }


def get_balance():
    
    hashflow_ETH_balance = w3.eth.get_balance(HASHFLOW_ADDRESS)
    MM_ETH_balance = w3.eth.get_balance(MM_ADDRESS)
    total_ETH_balance = hashflow_ETH_balance + MM_ETH_balance
    

    USDC_contract = w3.eth.contract(address=USDC_ADDRESS, abi=USDC_ABI)
    MM_USDC_balance = USDC_contract.functions.balanceOf(MM_ADDRESS).call() / 1e6
    

    return total_ETH_balance, MM_USDC_balance

def listen_to_executions():

    HASHFLOW_CONTRACT = w3.eth.contract(address=HASHFLOW_ADDRESS, abi=HASHFLOW_ABI)
    event_filter = HASHFLOW_CONTRACT.events.TradeExecuted.create_filter(fromBlock='latest')

    while True:
        for event in event_filter.get_new_entries():
            trader = event['args']['trader']
            amount = w3.fromWei(event['args']['baseAmount'], 'ether')

            print(f"Trade executed by {trader}, amount: {amount:.4f} ETH")
            total_ETH_balance, MM_USDC_balance = get_balance()
            print(f"ETH balance: {w3.fromWei(total_ETH_balance, 'ether')} ETH")
            print(f"USDC balance: {MM_USDC_balance} USDC")

        time.sleep(1)


if __name__ == "__main__":
    approve_usdc(amount=1_000_000)  # Разрешаем 1 млн USDC на контракт
    # listener_thread = threading.Thread(target=listen_to_executions, daemon=True)
    # listener_thread.start()
    uvicorn.run(app, host="0.0.0.0", port=8000)
