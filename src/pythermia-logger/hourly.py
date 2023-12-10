# this script is intended to be run hourly by cron
# this script downloads electricity prices from https://dashboard.elering.ee/assets/api-doc.html#/nps-controller/getPriceUsingGET
# stores them in the database
# calculates optimal heat pump parameters
# and sets them on an actual heat pump using modbus

import logging
from sys import argv
import sqlite3
import datetime
import requests
import json
from json import JSONDecodeError

from pythermiagenesis import ThermiaGenesis
from pythermiagenesis import ThermiaConnectionError
from pythermiagenesis.const import (
    REGISTERS,
    REG_INPUT,
    KEY_ADDRESS,
    KEY_DATATYPE,
    ATTR_HOLDING_COMFORT_WHEEL_SETTING,
    ATTR_HOLDING_START_TEMPERATURE_TAP_WATER,
    ATTR_HOLDING_STOP_TEMPERATURE_TAP_WATER,
    ATTR_HOLDING_HEATING_SEASON_STOP_TEMPERATURE,
)


import config  # import host, port, kind, prot, baud, btsz, prty, stbt, echo

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

PRICES_TABLE_NAME = config.PRICES_TABLE_NAME
THERMIA_TABLE_NAME = config.THERMIA_TABLE_NAME
THERMIA_DATABASE_NAME = config.THERMIA_DATABASE_NAME
PRICES_REQUEST = config.PRICES_REQUEST

create_table_header = f"""CREATE TABLE {PRICES_TABLE_NAME} (
ID INTEGER PRIMARY KEY,
TIMESTAMP INTEGER NOT NULL,
PRICE FLOAT NOT NULL
);
"""

check_exist_header = f"""SELECT COUNT(*)
FROM {PRICES_TABLE_NAME}
WHERE TIMESTAMP >= {{}};"""

insert_row_header = "INSERT INTO {} {} VALUES {};".format(
    PRICES_TABLE_NAME, "[TIMESTAMP,PRICE]", "{}"
)

# get and store prices


def process_prices():
    # form a query for prices

    today_date = datetime.datetime.now(datetime.UTC)
    tomorrow_date = today_date + datetime.timedelta(days=int(1))

    params = {
        "start": today_date.strftime("%Y-%m-%dT00:00:00.000Z"),
        "end": tomorrow_date.strftime("%Y-%m-%dT23:59:59.999Z"),
    }
    response = requests.get(
        PRICES_REQUEST["url"], params=params, headers=PRICES_REQUEST["headers"]
    )

    if not response.ok:
        _LOGGER.error(f"Cannot interpret server response: {e}")
        return None

    try:
        pricedata = response.json()
    except JSONDecodeError as e:
        _LOGGER.error(f"Cannot interpret server response: {e}")
        return None

    if pricedata["success"]:
        eeprices = pricedata["data"]["ee"]
        pricetimestamps = [eeprice["timestamp"] for eeprice in eeprices]
        pricevalues = [eeprice["price"] for eeprice in eeprices]

        try:
            con = sqlite3.connect(THERMIA_DATABASE_NAME)
            cur = con.cursor()

            # check if table exists
            cur.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{PRICES_TABLE_NAME}' LIMIT 1;"
            )
            result = cur.fetchall()
            if result != [(PRICES_TABLE_NAME,)]:
                _LOGGER.info(f"table does not exist ; creatning new one")
                _LOGGER.debug(f"table creation transaction:\n {create_table_header}")
                cur.execute(create_table_header)

            # for each timestamp value, check if it already exists:
            for pts, pval in zip(pricetimestamps, pricevalues):
                cur.execute(check_exist_header.format(pts))
                result = cur.fetchall()
                print(result)
                if result == [(0,)]:
                    insert_row_header.format([pts, pval])
                    _LOGGER.debug(f"record insertion transaction:\n {insert_row_req}")
                    cur.execute(insert_row_req)
            # con.commit()

        except con.Error as e:
            _LOGGER.error(f"Cannot connect or write to database: {e}")
            if con:
                con.rollback()
        finally:
            if cur:
                cur.close()
            if con:
                con.close()


if __name__ == "__main__":
    process_prices()
