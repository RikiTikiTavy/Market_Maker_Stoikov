import requests


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
        print('//////')
        print(f"price {price}", f"qty {qty}")
        print(f"best_bid ", bids[0][0])
        print("mid price ", mid_price)
        
        
        total_bid_qty += qty
        print('total_bid_qty', total_bid_qty)
        print('cumulative_bid_cost_usd ', cumulative_bid_cost_usd)
        cumulative_bid_cost_usd += (mid_price - price) * qty
        print('//////')
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

    print("k_bid ", k_bid)
    print("k_ask ", k_ask)



    best_bid = float(data['bids'][0][0])
    best_ask = float(data['asks'][0][0])

    spread = best_ask - best_bid
    if spread == 0:
        return 0.00001 # не делим на ноль

    k = 2 / spread

    print('old k ', k)

    return k_bid, k_ask


k_bid, k_ask = compute_k(20)
