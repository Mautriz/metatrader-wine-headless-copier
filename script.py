from __future__ import annotations

import MetaTrader5 as mt5
import os


import glob
import shutil

from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager

from importlib import import_module
from pydantic import BaseModel, RootModel
import asyncio

from typing import Literal
import datetime


class CopyAccountConfig(BaseModel):
    id: str
    login: int
    password: str
    server: str

    apply_sl: bool = False
    apply_tp: bool = False
    lot_ratio: float = 1.0
    mode: Literal["copy", "hedge"] = "copy"


class TimeRangeRequest(BaseModel):
    from_datetime: datetime.datetime
    to_datetime: datetime.datetime


class TestConnectionRequest(BaseModel):
    login: int
    password: str
    server: str


CopyAccountConfigs = RootModel[list[CopyAccountConfig]]


# Force flush on every print
def log(msg):
    print(msg, flush=True)


log("--- SCRIPT STARTING ---")

copy_accounts = CopyAccountConfigs.model_validate_json(os.getenv("COPY_ACCOUNTS", "[]"))


source_path = "/opt/wineprefix/drive_c/Program Files/meta"


def get_mt5_path(base_path: str = source_path) -> str:
    return f"{base_path}/terminal64.exe"


def add_installation(name: str):
    dest_path = f"/opt/wineprefix/drive_c/Program Files/{name}"

    if os.path.exists(dest_path):
        shutil.rmtree(dest_path)

    shutil.copytree(source_path, dest_path)

    # Clear MT5 bases and cache
    cache_patterns = [
        f"{dest_path}/Bases/*",
        f"{dest_path}/MQL5/Files/*",
        f"{dest_path}/MQL5/Cache/*",
    ]
    for pattern in cache_patterns:
        for path in glob.glob(pattern):
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.isfile(path):
                os.remove(path)

    return f"{dest_path}/terminal64.exe"


def add_mt5_module(name: str):
    base_path = "/opt/wineprefix/drive_c/Python/Lib/site-packages/"
    path = f"{base_path}/{name}"

    if os.path.exists(path):
        shutil.rmtree(path)

    shutil.copytree(f"{base_path}/MetaTrader5", path)

    return import_module(name)


i = 100


def add_module_and_init(
    login: str | int,
    password: str,
    server: str,
):
    global i
    i = i + 1

    installation_name = f"meta{i}"
    log(f"Adding installation {installation_name}")
    exe_path = add_installation(installation_name)
    log(f"Installation path: {exe_path}")

    mod = add_mt5_module(f"mt5lib{i + 5}")

    log(f"Python module initialize {login}")

    initialized = mod.initialize(
        path=exe_path,
        login=int(login),
        password=password,
        server=server,
        portable=True,
        timeout=5_000,
    )

    log(f"Initialized: {initialized}")

    if not initialized:
        log(f"Init failed! {i}")
        log(f"Error code: {mt5.last_error()}")

    log(
        f"Deals count for account: {len(mod.history_deals_get(
            0, int((datetime.datetime.now() + datetime.timedelta(days=1)).timestamp())
        ) or [])}"
    )

    return mod


other_mt5s = [
    add_module_and_init(
        login=account.login,
        password=account.password,
        server=account.server,
    )
    for account in copy_accounts.root
]


def round_to_step(value: float, step: float):
    return round(value / step) * step


async def copy_trading_loop():
    position_sizes: dict[int, float] = {}
    step_size_per_symbol: dict[str, float] = {}

    while True:
        try:

            info = mt5.positions_get()
            for pos in info:
                position_sizes[pos.ticket] = pos.volume

            # Set to 0 missing tickets and del tickes already at 0
            current_ticket_ids = [p.ticket for p in info]
            for ticket in list(position_sizes.keys()):
                if ticket not in current_ticket_ids:
                    position_sizes[ticket] = 0

            other_accounts_position_sizes: list[dict[int, float]] = [
                {} for _ in other_mt5s
            ]
            for i, x in enumerate(other_mt5s):
                other_positions = x.positions_get()
                for pos in other_positions:
                    other_accounts_position_sizes[i][pos.magic] = pos.volume

            for ticket, size in position_sizes.items():

                base_position = next((p for p in info if p.ticket == ticket), None)
                for i, _ in enumerate(other_mt5s):
                    other_size = other_accounts_position_sizes[i].get(ticket, 0)
                    other_account = other_mt5s[i]

                    positions = other_account.positions_get()
                    position = next((p for p in positions if p.magic == ticket), None)

                    mixed_position = base_position or position
                    if mixed_position is None:
                        continue

                    adjusted_base_size = round_to_step(
                        size * copy_accounts.root[i].lot_ratio,
                        step_size_per_symbol.get(mixed_position.symbol, 0.01),
                    )

                    other_accounts_position_sizes[i][ticket] = adjusted_base_size

                    type = (
                        mt5.POSITION_TYPE_SELL
                        if mixed_position.type == mt5.POSITION_TYPE_BUY
                        else mt5.POSITION_TYPE_BUY
                    )

                    if other_size > adjusted_base_size and position is not None:
                        type = (
                            mt5.POSITION_TYPE_BUY
                            if position.type == mt5.POSITION_TYPE_SELL
                            else mt5.POSITION_TYPE_SELL
                        )

                    volume = abs(
                        round_to_step(
                            adjusted_base_size - other_size,
                            step_size_per_symbol.get(mixed_position.symbol, 0.01),
                        )
                    )

                    if volume == 0:
                        continue

                    log(
                        f"mixed_position.type: {mixed_position.type}, type: {type}, size: {size}, adjusted_base_size: {adjusted_base_size}, other_size: {other_size}, volume: {volume}"
                    )

                    req = OrderRequest(
                        action=1,
                        magic=ticket,
                        symbol=mixed_position.symbol,
                        volume=volume,
                        comment="",
                        deviation=20,
                        expiration=None,
                        order=None,
                        position=position.ticket if position else None,
                        position_by=None,
                        price=None,
                        sl=None,
                        stoplimit=None,
                        tp=None,
                        type=type,
                        type_filling=mt5.ORDER_FILLING_FOK,
                        type_time=mt5.ORDER_TIME_GTC,
                    ).model_dump(exclude_none=True)

                    log("Sending request to account " + str(i))
                    log(req)

                    result = other_account.order_send(req)

                    if result.retcode != mt5.TRADE_RETCODE_DONE:
                        log(
                            f"Account {i} - Order failed, retcode={result.retcode}, comment={result.comment} {other_account.last_error()}"
                        )

            await asyncio.sleep(float(os.getenv("LOOP_DELAY_SECONDS", 1.0)))
        except Exception as e:
            log("CRASH IN COPY LOOP")
            log(e)
            await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        path = get_mt5_path()
        # Check if file exists first
        if not os.path.exists(path):
            log(f"FATAL: {path} not found!")

        log("Initializing master MT5")

        initialized = mt5.initialize(
            path=path,
            login=int(os.getenv("LOGIN", "")),
            password=os.getenv("PASSWORD", ""),
            server=os.getenv("SERVER", ""),
            portable=True,
        )

        if not initialized:
            log("Init failed!")
            log(f"Error code: {mt5.last_error()}")
        else:
            log("Success!")
            print(mt5.account_info())

    except Exception as e:
        log(f"CRASH: {str(e)}")

    task = asyncio.create_task(copy_trading_loop())

    yield
    task.cancel()
    mt5.shutdown()


master_id = os.getenv("MASTER_ID", "master")

app = FastAPI(lifespan=lifespan)


@app.get("/healthz")
async def health_check():
    return {"status": "ok"}


@app.get("/")
async def account_info():
    infos = {
        copy_accounts.root[i].id: mod.account_info()._asdict()
        for i, mod in enumerate(other_mt5s)
    } | {master_id: mt5.account_info()._asdict()}

    return infos


@app.post("/test-connection")
async def test_connection(data: TestConnectionRequest):
    initialized = mt5.login(
        # path=get_mt5_path(),
        login=int(data.login),
        password=data.password,
        server=data.server,
        # portable=True,
    )

    if not initialized:
        return {"success": False, "error": f"Init failed! {mt5.last_error()}"}
    else:
        account_info = mt5.account_info()
        return {"success": True, "account_info": account_info._asdict()}


@app.post("/get-deals")
async def get_deals(data: TimeRangeRequest):
    from_ = int(data.from_datetime.timestamp())
    to_ = int(data.to_datetime.timestamp())

    log(f"Getting deals from {from_} to {to_}")

    print(len(mt5.history_deals_get(from_, to_)))
    print(len(other_mt5s[0].history_deals_get(from_, to_)))

    return {
        "a": len(mt5.history_deals_get(from_, to_)),
        "b": len(other_mt5s[0].history_deals_get(from_, to_)),
    }

    # deals = {
    #     copy_accounts.root[i].id: mod.history_deals_get(from_, to_)
    #     for i, mod in enumerate(other_mt5s)
    # } | {master_id: mt5.history_deals_get(from_, to_)}

    # return {
    #     id: ([deal._asdict() for deal in deals_list] if deals_list is not None else [])
    #     for id, deals_list in deals.items()
    # }


@app.post("/get-positions")
async def get_positions():
    positions = {
        copy_accounts.root[i].id: mod.positions_get()
        for i, mod in enumerate(other_mt5s)
    } | {master_id: mt5.positions_get()}
    return {
        id: (
            [position._asdict() for position in positions_list]
            if positions_list is not None
            else []
        )
        for id, positions_list in positions.items()
    }


@app.post("/get-orders")
async def get_orders(
    data: TimeRangeRequest,
):
    from_ = int(data.from_datetime.timestamp())
    to_ = int(data.to_datetime.timestamp())

    orders = {
        copy_accounts.root[i].id: mod.history_orders_get(from_, to_)
        for i, mod in enumerate(other_mt5s)
    } | {master_id: mt5.history_orders_get(from_, to_)}

    return {
        id: (
            [order._asdict() for order in orders_list]
            if orders_list is not None
            else []
        )
        for id, orders_list in orders.items()
    }


class OrderRequest(BaseModel):
    # TRADE_ACTION_DEAL
    # TRADE_ACTION_PENDING
    # TRADE_ACTION_SLTP
    # TRADE_ACTION_MODIFY
    # TRADE_ACTION_REMOVE
    # TRADE_ACTION_CLOSE_BY
    action: Literal[1, 5, 6, 7, 8, 10]
    magic: int | None
    order: int | None
    symbol: str
    volume: float | None
    price: float | None
    stoplimit: float | None
    sl: float | None
    tp: float | None
    deviation: int | None
    expiration: int | None
    comment: str | None
    deviation: int | None
    position: int | None
    position_by: int | None
    # ORDER_TIME_GTC
    # ORDER_TIME_DAY
    # ORDER_TIME_SPECIFIED
    # ORDER_TIME_SPECIFIED_DAY
    type_time: Literal[0, 1, 2, 3] | None

    # ORDER_FILLING_FOK
    # ORDER_FILLING_IOC
    # ORDER_FILLING_RETURN
    # ORDER_FILLING_BOC
    type_filling: Literal[0, 1, 2, 3] | None
    type: int | None


@app.get("/symbol-info-tick/{symbol}")
async def tick_info(symbol: str):
    mt5.symbol_select(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise Exception(f"Symbol {symbol} not found")

    return tick._asdict()


@app.get("/symbol-info/{symbol}")
async def symbol_info(symbol: str):
    info = mt5.symbol_info(symbol)
    if info is None:
        raise Exception(f"Symbol {symbol} not found")

    return info._asdict()


@app.post("/send-order")
async def send_order(order_request: OrderRequest):
    mt5req = order_request.model_dump(exclude_none=True)
    result = mt5.order_send(mt5req)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        raise Exception(
            f"Order failed, retcode={result.retcode}, comment={result.comment} {mt5.last_error()}"
        )

    return result._asdict()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
