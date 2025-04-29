./deploy_usdc.sh
echo "USDC deployed"

./deploy_hashflow.sh
echo "Hashflow deployed"

python send_eth.py
echo "ETH send to Hashflow"

python send_USDC.py
echo "USDC send to Trader"

