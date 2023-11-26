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

import config  # import host, port, kind, prot, baud, btsz, prty, stbt, echo

THERMIA_TABLE_NAME = config.THERMIA_TABLE_NAME
THERMIA_DATABASE_NAME = config.THERMIA_DATABASE_NAME
_LOGGER = logging.getLogger(__name__)


# logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=config.logging_level)

create_table_header = f"""CREATE TABLE {THERMIA_TABLE_NAME} (
ID INTEGER PRIMARY KEY,
TIMESTAMP INTEGER NOT NULL,
"""
insert_row_header = "INSERT INTO {} {} VALUES {};".format(
    THERMIA_TABLE_NAME, "{}", "{}"
)


def dtp_convert(val):
    if type(val) is str:
        return "TEXT"
    if type(val) is int:
        return "INTEGER"
    if type(val) is float:
        return "FLOAT"
    if type(val) is bool:
        return "INTEGER"


def make_create_table_req(data_items):
    dblines = []
    for i, (name, val) in enumerate(data_items):
        dtp_txt = dtp_convert(val)
        dblines.append(f"{name}  {dtp_txt}")
    dbreq = create_table_header + ",\n".join(dblines) + "\n);"
    return dbreq


async def main():
    thermia = ThermiaGenesis(
        config.host,
        protocol=config.prot,
        port=config.port,
        kind=config.kind,
        delay=0.01,
        baudrate=config.baud,
        bytesize=config.btsz,
        parity=config.prty,
        stopbits=config.stbt,
        handle_local_echo=config.echo,
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

        _LOGGER.info(f"Data available: {thermia.available}")

        create_table_req = make_create_table_req(thermia.data.items())

        names, vals = zip(*thermia.data.items())
        names = ("TIMESTAMP",) + names
        vals = (str(int(datetime.timestamp(timenow))),) + vals
        insert_row_req = insert_row_header.format(names, vals)

        try:
            con = sqlite3.connect(THERMIA_DATABASE_NAME)
            cur = con.cursor()

            # check if table exists
            cur.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{THERMIA_TABLE_NAME}' LIMIT 1;"
            )
            result = cur.fetchall()
            if result != [(THERMIA_TABLE_NAME,)]:
                _LOGGER.info(f"table does not exist ; creatning new one")
                _LOGGER.debug(f"db creation transaction:\n {create_table_req}")
                cur.execute(create_table_req)

            _LOGGER.debug(f"record insertion transaction:\n {insert_row_req}")
            cur.execute(insert_row_req)
            con.commit()

        except con.Error as e:
            _LOGGER.error(f"Cannot connect or write to database: {e}")
            if con:
                con.rollback()
        finally:
            if cur:
                cur.close()
            if con:
                con.close()

        # get num of entries to the db to see if anything happens
        query_count = f"SELECT COUNT(*) FROM {THERMIA_TABLE_NAME} ;"
        query_lastrecord = f"SELECT ID,TIMESTAMP FROM {THERMIA_TABLE_NAME} ORDER BY TIMESTAMP DESC LIMIT 1;"
        try:
            con = sqlite3.connect(THERMIA_DATABASE_NAME)
            cur = con.cursor()
            cur.execute(query_count)
            result = cur.fetchone()
            row_count = result[0]
            _LOGGER.info(f"total entries now: {row_count}")

            if logging.DEBUG >= logging.root.level:
                cur.execute(query_lastrecord)
                result = cur.fetchone()
                _LOGGER.debug(f"last entry: \n {result}")
        except con.Error as e:
            _LOGGER.error(f"Cannot connect or write to database: {e}")
            if con:
                con.rollback()
        finally:
            if cur:
                cur.close()
            if con:
                con.close()


# for i, (name, val) in enumerate():
#    print(f"{REGISTERS[name][KEY_ADDRESS]}\t{name}\t{val}")


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.close()
