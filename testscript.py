from pydantic import BaseModel
import asyncio
import MetaTrader5 as mt5
from datetime import datetime, timedelta


class CopyAccountConfig(BaseModel):
    login: int
    password: str
    server: str

    apply_sl: bool = False
    apply_tp: bool = False
    lot_ratio: float = 1.0


mt5.initialize()


# mt5.symbol_select("BTCUSD")
# print(mt5.symbol_info("BTCUSD")._asdict())

# orders = [o._asdict() for o in mt5.orders_get()]
# print("BEFORE:", orders)

# if orders:
#     ticket = orders[0]["ticket"]
#     symbol = orders[0]["symbol"]

#     request = {
#         "action": mt5.TRADE_ACTION_SLTP,
#         "order": ticket,
#         # "symbol": symbol,
#         # "type_time": mt5.ORDER_TIME_GTC,
#     }

#     result = mt5.order_send(request)

#     # Check what actually happened
#     if result is None:
#         print("order_send returned None — error:", mt5.last_error())
#     elif result.retcode != mt5.TRADE_RETCODE_DONE:
#         print(f"Failed to cancel. retcode: {result.retcode}, comment: {result.comment}")
#         print("Full result:", result)
#     else:
#         print("Order cancelled successfully:", result)

# print("AFTER")
# orders_after = [o._asdict() for o in mt5.orders_get()]
# print(orders_after)

ticket = 36935349


def change_stop_loss():
    # Get the open position by ticket
    positions = mt5.positions_get()

    for pos in positions:
        # position.comment might have this format "xax 25000 25000", so we can parse it to get the current SL and TP if needed
        position_info = pos.comment
        if not position_info.startswith("xax"):
            continue
        sl_points, tp_points = map(float, position_info.split()[1:3])

        point = mt5.symbol_info(pos.symbol).point
        price_open = pos.price_open

        if pos.type == mt5.POSITION_TYPE_SELL:
            new_sl = price_open + sl_points * point
            new_tp = price_open - tp_points * point
        else:
            new_sl = price_open - sl_points * point
            new_tp = price_open + tp_points * point

        if pos.tp == new_tp and pos.sl == new_sl:
            continue

        print("HERE")

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": pos.symbol,
            "position": pos.ticket,
            "sl": new_sl,  # ⚠️ This is a PRICE, not points!
            "tp": new_tp,  # ⚠️ This is a PRICE, not points!
            "comment": "CIAOOOO",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(
                f"Failed to modify SL. Error code: {result.retcode}, {result.comment}"
            )
            return False

        print(f"SL updated to {new_sl} for ticket {ticket}")


change_stop_loss()


# def get_info(symbol):
#     """https://www.mql5.com/en/docs/integration/python_metatrader5/mt5symbolinfo_py"""
#     # get symbol properties
#     info = mt5.symbol_info(symbol)
#     return info


# def open_trade(action, symbol, lot, sl_points, tp_points, deviation):
#     """https://www.mql5.com/en/docs/integration/python_metatrader5/mt5ordersend_py"""
#     # prepare the buy request structure

#     if action == "buy":
#         trade_type = mt5.ORDER_TYPE_BUY
#         price = mt5.symbol_info_tick(symbol).ask
#     elif action == "sell":
#         trade_type = mt5.ORDER_TYPE_SELL
#         price = mt5.symbol_info_tick(symbol).bid
#     point = mt5.symbol_info(symbol).point

#     print(price - sl_points * point, price + tp_points * point)

#     buy_request = {
#         "action": mt5.TRADE_ACTION_DEAL,
#         "symbol": symbol,
#         "volume": lot,
#         "type": trade_type,
#         "price": price,
#         "sl": price - sl_points * point,
#         "tp": price + tp_points * point,
#         "deviation": deviation,
#         "magic": 7667,
#         "comment": "sent by python",
#         "type_time": mt5.ORDER_TIME_GTC,  # good till cancelled
#         "type_filling": mt5.ORDER_FILLING_FOK,
#     }
#     # send a trading request
#     result = mt5.order_send(buy_request)

#     print(result)

#     if result.retcode != mt5.TRADE_RETCODE_DONE:
#         print(f"Order failed, retcode={result.retcode}, comment={result.comment}")

#     return result, buy_request


# def close_trade(action, buy_request, result, deviation):
#     """https://www.mql5.com/en/docs/integration/python_metatrader5/mt5ordersend_py"""
#     # create a close request
#     symbol = buy_request["symbol"]
#     if action == "buy":
#         trade_type = mt5.ORDER_TYPE_BUY
#         price = mt5.symbol_info_tick(symbol).ask
#     elif action == "sell":
#         trade_type = mt5.ORDER_TYPE_SELL
#         price = mt5.symbol_info_tick(symbol).bid
#     position_id = result.order
#     lot = buy_request["volume"]

#     close_request = {
#         "action": mt5.TRADE_ACTION_DEAL,
#         "symbol": symbol,
#         "volume": lot,
#         "type": trade_type,
#         "position": position_id,
#         "price": price,
#         "deviation": deviation,
#         "magic": 7667,
#         "comment": "python script close",
#         "type_time": mt5.ORDER_TIME_GTC,  # good till cancelled
#         "type_filling": mt5.ORDER_FILLING_RETURN,
#     }
#     # send a close request
#     result = mt5.order_send(close_request)


# open_trade("buy", "BTCUSD", 0.01, 1000, 1000, 20)
