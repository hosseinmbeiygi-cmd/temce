from __future__ import annotations

from backtesting.abm.order_book import OrderBook, OrderBookEntry, OrderSide, OrderType, Trade


class MatchingEngine:
    def match(self, entry: OrderBookEntry, orderbook: OrderBook) -> list[Trade]:
        trades: list[Trade] = []
        if entry.side == OrderSide.BUY:
            trades = self._match_buy(entry, orderbook)
        else:
            trades = self._match_sell(entry, orderbook)
        return trades

    def _match_buy(self, buy: OrderBookEntry, orderbook: OrderBook) -> list[Trade]:
        trades: list[Trade] = []
        while buy.remaining > 0:
            best_ask = orderbook.best_ask
            if best_ask <= 0 or (buy.order_type == OrderType.LIMIT and best_ask > buy.price):
                break
            ask_entry = orderbook._asks[0] if orderbook._asks else None
            if ask_entry is None or ask_entry.remaining <= 0:
                break
            matched_qty = min(buy.remaining, ask_entry.remaining)
            trade_price = ask_entry.price
            trade = Trade(
                buy_order_id=buy.order_id,
                sell_order_id=ask_entry.order_id,
                price=trade_price,
                quantity=matched_qty,
                buyer_id=buy.agent_id,
                seller_id=ask_entry.agent_id,
            )
            trades.append(trade)
            buy.remaining -= matched_qty
            ask_entry.remaining -= matched_qty
            if ask_entry.remaining <= 0:
                import heapq

                heapq.heappop(orderbook._asks)
            orderbook._trades.append(trade)
        return trades

    def _match_sell(self, sell: OrderBookEntry, orderbook: OrderBook) -> list[Trade]:
        trades: list[Trade] = []
        while sell.remaining > 0:
            best_bid = orderbook.best_bid
            if best_bid <= 0 or (sell.order_type == OrderType.LIMIT and best_bid < sell.price):
                break
            bid_entry = orderbook._bids[0] if orderbook._bids else None
            if bid_entry is None or bid_entry.remaining <= 0:
                break
            matched_qty = min(sell.remaining, bid_entry.remaining)
            trade_price = bid_entry.price
            trade = Trade(
                buy_order_id=bid_entry.order_id,
                sell_order_id=sell.order_id,
                price=trade_price,
                quantity=matched_qty,
                buyer_id=bid_entry.agent_id,
                seller_id=sell.agent_id,
            )
            trades.append(trade)
            sell.remaining -= matched_qty
            bid_entry.remaining -= matched_qty
            if bid_entry.remaining <= 0:
                import heapq

                heapq.heappop(orderbook._bids)
            orderbook._trades.append(trade)
        return trades
