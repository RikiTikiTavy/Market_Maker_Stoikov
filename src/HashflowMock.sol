// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";


contract HashflowMock {
    event TradeExecuted(
        address indexed trader,
        address indexed maker,
        uint256 baseAmount,
        uint256 quoteAmount,
        uint256 price
    );

    struct Quote {
        uint256 baseAmount;
        uint256 quoteAmount;
        uint256 price;
        uint256 expiry;
        address maker;
        address trader;
        bytes signature;
    }

    IERC20 public usdc;

    constructor(address _usdc) {
        usdc = IERC20(_usdc);
    }

    function trade(Quote calldata q, bool isSellingETH) external payable {


        if (isSellingETH) {
            // Trader sends ETH, receives USDC
            require(msg.value >= q.baseAmount, "Not enough ETH sent");
            require(usdc.balanceOf(q.maker) >= q.quoteAmount, "Maker has insufficient USDC");
            require(usdc.allowance(q.maker, address(this)) >= q.quoteAmount, "Maker didn't approve USDC");

            usdc.transferFrom(q.maker, q.trader, q.quoteAmount);
            payable(q.maker).transfer(msg.value);

        } else {
            // Trader sends USDC, receives ETH
            require(usdc.balanceOf(q.trader) >= q.quoteAmount, "Trader has insufficient USDC");
            require(usdc.allowance(q.trader, address(this)) >= q.quoteAmount, "Trader didn't approve USDC");

            // Trader sends USDC, receives ETH
            uint256 ethBalance = address(this).balance;

            require(ethBalance >= q.baseAmount, "Not enough ETH in hashflow");

            usdc.transferFrom(q.trader, q.maker, q.quoteAmount);
            payable(q.trader).transfer(q.baseAmount);
        }

        emit TradeExecuted(q.trader, q.maker, q.baseAmount, q.quoteAmount, q.price);
    }

    receive() external payable {}
}
