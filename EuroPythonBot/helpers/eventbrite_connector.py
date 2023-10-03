import logging
import os
import pandas as pd
import aiofiles

from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from time import time
from typing import Dict, List
from unidecode import unidecode

from configuration import Config, Singleton
from error import AlreadyRegisteredError, NotFoundError

_logger = logging.getLogger(f"bot.{__name__}")


def sanitize_string(input_string: str) -> str:
    """Process the name to make it more uniform."""
    return unidecode(input_string.replace(" ", "").lower())


class EventbriteOrder(metaclass=Singleton):
    def __init__(self):
        self.config = Config()

        self.id_to_name = None
        self.orders = {}
        self.last_fetch = None

        self.registered_file = getattr(self.config, "REGISTERED_LOG_FILE", "./registered_log.txt")
        self.REGISTERED_SET = set()

    def load_registered(self):
        try:
            f = open(self.registered_file, "r")
            registered = [reg.strip() for reg in f.readlines()]
            self.REGISTERED_SET = set(registered)
            f.close()
        except Exception:
            _logger.exception("Cannot load registered data, starting from scratch. Error:")

    async def fetch_data(self) -> None:
        """Fetch data from Pretix, store id_to_name mapping and formated orders internally"""

        _logger.info("Fetching IDs names from pretix")

        raw_orders = pd.read_csv("report.csv", encoding="utf-8")[["Order #", "First Name", "Last Name", "Ticket Type"]]
        print(raw_orders)

        orders = {}
        for idx, row in raw_orders.iterrows():
            order_number = row["Order #"]
            name = f'{row["First Name"]} {row["Last Name"]}'
            ticket_type = row["Ticket Type"]

            orders[f"{order_number}-{sanitize_string(name)}"] = ticket_type

        self.orders = orders
        self.last_fetch = datetime.now()

    async def get_ticket_type(self, order: str, full_name: str) -> str:
        """With user input `order` and `full_name`, check for their ticket type"""

        key = f"{order}-{sanitize_string(input_string=full_name)}"
        if self.validate_key(key):
            if key in self.orders:
                async with aiofiles.open(self.registered_file, mode="a") as f:
                    await f.write(f"{key}\n")
                return self.orders[key]
            else:
               raise NotFoundError(f"No ticket found - inputs: {order=}, {full_name=}")


    async def get_roles(self, name: str, order: str) -> List[int]:
        ticket_type = await self.get_ticket_type(full_name=name, order=order)
        return self.config.TICKET_TO_ROLE.get(ticket_type)

    def validate_key(self, key: str) -> bool:
        if key in self.REGISTERED_SET:
            raise AlreadyRegisteredError(f"Ticket already registered - id: {key}")
        return True
