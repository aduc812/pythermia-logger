# from nordpool import elspot

# prices_spot = elspot.Prices()

# pprint(prices_spot.hourly(areas=["EE"]))

import asyncio
import logging
from sys import argv
import sqlite3
from datetime import datetime, UTC

from pythermiagenesis import ThermiaGenesis
from pythermiagenesis import ThermiaConnectionError
from pythermiagenesis.const import (
    REGISTERS,
    REG_INPUT,
    KEY_ADDRESS,
    KEY_DATATYPE,
    ATTR_COIL_ENABLE_HEAT,
    ATTR_COIL_ENABLE_BRINE_IN_MONITORING,
)

LOG_TABLE_NAME = "parameters"


def dtp_convert(val):
    if type(val) is str:
        return "TEXT"
    if type(val) is int:
        return "INTEGER"
    if type(val) is float:
        return "FLOAT"
    if type(val) is bool:
        return "INTEGER"


# heatpum IP address/hostname
HOST = "10.0.20.8"
PORT = 502
# logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.INFO)

create_table_header = """CREATE TABLE parameters(
ID INTEGER PRIMARY KEY AUTOINCREMENT,
TIMESTAMP INTEGER NOT NULL,
"""
insert_row_header = "INSERT INTO parameters {} VALUES {};"


def create_table(data_items):
    dblines = []
    for i, (name, val) in enumerate(data_items):
        dtp_txt = dtp_convert(val)
        dblines.append(f"{name}  {dtp_txt}")
    dbreq = create_table_header + ",\n".join(dblines) + "\n);"
    return dbreq


async def main():
    host = argv[1] if len(argv) > 1 else HOST
    port = argv[2] if len(argv) > 2 else PORT
    kind = argv[3] if len(argv) > 3 else "inverter"
    prot = argv[4] if len(argv) > 4 else "TCP"

    # RTU arguments; leave default for TCP connection
    baud = int(argv[5]) if len(argv) > 5 else 19200
    btsz = int(argv[6]) if len(argv) > 6 else 8
    prty = argv[7] if len(argv) > 7 else "E"
    stbt = int(argv[8]) if len(argv) > 8 else 1
    echo = bool(argv[9]) if len(argv) > 9 else False

    # argument kind: inverter - for Diplomat Inverter
    #                mega     - for Mega
    # argument prot: "TCP"    - for TCP/IP
    #                "RTU"    - for RTU over RS485

    thermia = ThermiaGenesis(
        host,
        protocol=prot,
        port=port,
        kind=kind,
        delay=0.15,
        baudrate=baud,
        bytesize=btsz,
        parity=prty,
        stopbits=stbt,
        handle_local_echo=echo,
    )
    try:
        # Get all register types
        # await thermia.async_update()
        # Get only input registers
        # await thermia.async_update([REG_INPUT])
        # Get one specific register
        # await thermia.async_update(only_registers=[ATTR_COIL_ENABLE_BRINE_IN_MONITORING, ATTR_COIL_ENABLE_HEAT])
        await thermia.async_update([])

    except ThermiaConnectionError as error:
        print(f"Failed to connect: {error.message}")
        return
    except ConnectionError as error:
        print(f"Connection error {error}")
        return

    if thermia.available:
        timenow = datetime.now(UTC)
        print(f"Data available: {thermia.available}")
        print(f"Model: {thermia.model}")
        print(f"Firmware: {thermia.firmware}")

        create_table_req = create_table(thermia.data.items())
        con = sqlite3.connect("/home/bms/thermia-log.db")
        cur = con.cursor()

        # check if table exists
        cur.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{LOG_TABLE_NAME}' LIMIT 1;"
        )
        result = cur.fetchall()
        if result != [(LOG_TABLE_NAME,)]:
            print("table does not exist: returned {result}")
            print(create_table_req)
            cur.execute(create_table_req)

        names, vals = zip(*thermia.data.items())
        names = ("TIMESTAMP",) + names
        vals = (str(int(datetime.timestamp(timenow))),) + vals
        insert_row_req = insert_row_header.format(names, vals)
        # print(insert_row_req)
        cur.execute(insert_row_req)

        query = f"SELECT COUNT(*) FROM {LOG_TABLE_NAME} ;"
        cur.execute(query)
        result = cur.fetchone()
        row_count = result[0]
        print(f"total entries now: {row_count}")

        cur.close()
        con.close()


# for i, (name, val) in enumerate():
#    print(f"{REGISTERS[name][KEY_ADDRESS]}\t{name}\t{val}")


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.close()
