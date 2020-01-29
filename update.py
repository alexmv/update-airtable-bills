#!/usr/bin/env python
import datetime
import os
import re
import time

import pyopenstates
from airtable import Airtable

# The specific Airtable to update
AIRTABLE_BILLS_ID = "appVuarUc0kCpjwWn"

# API keys to read from OpenStates and write to Airtable
AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", None)
OPENSTATES_API_KEY = os.environ.get("OPENSTATES_API_KEY", None)


# OpenStates allows 2 requests/sec, with bursts of 10.  Wrap an
# arbitrary function such that it conforms to that rate limit
def ratelimit(func, rate=2.0, burst=10.0):
    requests = []

    def delayed(**kwargs):
        now = time.clock_gettime(time.CLOCK_MONOTONIC)
        if len(requests) >= burst:
            last = requests.pop(0)
            if now < last + (burst / rate):
                time.sleep(last + (burst / rate) - now)
                now = time.clock_gettime(time.CLOCK_MONOTONIC)
        requests.append(now)
        return func(**kwargs)

    return delayed


def main():
    # Check that we have got our API keys configured right
    if not AIRTABLE_API_KEY or not re.search(r"[a-z]", AIRTABLE_API_KEY):
        raise ValueError("AIRTABLE_API_KEY is not configured")
    if not OPENSTATES_API_KEY or not re.search(r"[a-z]", OPENSTATES_API_KEY):
        raise ValueError("OPENSTATES_API_KEY is not configured")

    # Set up the OpenStates API, and the rate-limited bill-fetching
    pyopenstates.set_api_key(OPENSTATES_API_KEY)
    get_bill = ratelimit(pyopenstates.get_bill)

    # Set up to talk to Airtable
    state_bills = Airtable(AIRTABLE_BILLS_ID, "State", api_key=AIRTABLE_API_KEY)
    assert state_bills
    state_bill_updates = Airtable(
        AIRTABLE_BILLS_ID, "State status", api_key=AIRTABLE_API_KEY
    )
    assert state_bill_updates

    # Iterate through all of the bills listed in the "State"
    listed_bills = state_bills.get_all(sort="Bill")
    for bill in listed_bills:
        # Each "bill" is a dictionary; "fields" contains a dict with a
        # key/value for each non-empty column.

        # Some rows don't have a bill ID (yet)
        if "Bill" not in bill["fields"]:
            continue

        # Re-format the bill identifier to suit how OpenStates wants
        # it; letters, then a space, then numbers
        bill_id = re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", bill["fields"]["Bill"])

        # Figure out which legislative session this is in.  If it's
        # not divisible by two (odd), then it's that year and the
        # next; if it's even, it's the year before and then that year.
        year = int(bill["fields"]["Year introduced"])
        if year % 2 != 0:
            leg_year = "{}{}".format(year, year + 1)
        else:
            leg_year = "{}{}".format(year - 1, year)

        # Get what data we can from OpenStates
        bill_data = get_bill(state="CA", term=leg_year, bill_id=bill_id)
        latest_openstates_action = bill_data["action_dates"]["last"].date()

        # Determine the latest update in Airtable for this bill
        latest_airtable_update = None
        if "Last update" in bill["fields"]:
            latest_airtable_update = datetime.date.fromisoformat(
                bill["fields"]["Last update"]
            )

        # If we don't have any Airtable update rows yet, pull in the
        # full history.  We can also say "no updates" if the most
        # recent date in OpenStates is _before_ the most recent date
        # in Airtable
        if (
            latest_airtable_update
            and latest_openstates_action <= latest_airtable_update
        ):
            print("{}: No updates".format(bill_id))
            continue  # Go to the next bill

        # Keep track of which "reading" the bill is currently on
        reading = bill["fields"].get("Reading", None)

        # Keep track of the number of updates:
        bill_update_count = 0

        for update_data in bill_data["actions"]:
            # Parse out the date from OpenStates; these are _all_
            # updates on the bill, so we'll skip updates that are
            # prior to the latest row we have in Airtable
            update_date = datetime.date.fromisoformat(update_data["date"].split(" ")[0])
            if latest_airtable_update and update_date <= latest_airtable_update:
                continue  # Go to next update on this bill

            # Advance which "reading" the bill is in
            if not reading:
                reading = "First reading"
            if "bill:reading:2" in update_data["type"] and reading == "First reading":
                reading = "Second reading"
            if "bill:reading:3" in update_data["type"] and reading == "Second reading":
                reading = "Third reading"

            # Translate lower/upper chambers into Assembly/Senate
            location = "Assembly" if update_data["actor"] == "lower" else "Senate"

            # The row we want to insert in the "State status" table:
            update = {
                "Bill": [bill["id"]],
                "Status": bill["fields"].get("Status", "Moving"),
                "Status notes": update_data["action"],
                "Date last status change": update_date.isoformat(),
                "Location": location,
                "Reading": reading,
            }
            state_bill_updates.insert(update)

            bill_update_count += 1
        print(
            "{}: {} update{}".format(
                bill_id, bill_update_count, "" if bill_update_count == 1 else "s"
            )
        )

    print()
    print("See https://airtable.com/{}".format(AIRTABLE_BILLS_ID))


if __name__ == "__main__":
    main()
