"""Regenerate the sample CSVs. Deterministic.

Run from the repo root:  python samples/generate.py

    orders.csv     ~1,500 rows over 2023-2024, dirty on purpose, ACCEPTED
    customers.csv  clean, the control case
    bad.csv        dirty enough to be REJECTED

Everything random is drawn from ``SEED``, so the files are byte-identical on
every run. That matters more than it looks: the expected answers in the
verification runs and in the tests are specific numbers, and a sample that
quietly changed would turn a correct answer into a failing check with no code
change to blame.

Why orders.csv is dirty rather than clean: a clean sample only exercises the
happy path, so the preprocessing report, the excluded-column handling and the
type-conversion notice are never seen until a real user finds them. Each flaw
below aims at one code path, and the thresholds in validation.py decide how
far each one can go.
"""

import csv
import pathlib
import random
from datetime import date, timedelta

SEED = 20260111
HERE = pathlib.Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# orders.csv
# ---------------------------------------------------------------------------
#
# Shape: two full years so "per month" and "only 2024" are both real
# questions — every one of the 24 months has rows.
#
# Thresholds this file steers between (validation.py):
#
#   MISSING_COLUMN_THRESHOLD    0.70  a column above this is EXCLUDED
#   MISSING_DATASET_THRESHOLD   0.40  a dataset above this is REJECTED
#   DUPLICATE_WARNING_THRESHOLD 0.10  above this: a warning
#   DUPLICATE_REJECT_THRESHOLD  0.50  above this: rejected
#   TYPE_CONVERSION_THRESHOLD   0.95  BELOW this the column stays text
#
# 1. customer_phone ~75% missing: above the column threshold, so it is
#    excluded with a reason and the agent is told why rather than silently
#    losing a column. One column of nine keeps the dataset mean near 9%, far
#    below the 40% that would reject the file.
#
# 2. quantity arrives as TEXT. Some values are whitespace-padded and 4% are
#    words, so 96% parse — just clearing the 95% conversion threshold, which
#    means the column IS converted and the bad rows become NaN. Push the bad
#    share past 5% and the column stays text, at which point summing it
#    CONCATENATES and "highest total quantity" is silently wrong rather than
#    merely short a few rows.
#
# 3. 195 duplicate rows of 1,500 is 13%: above the 10% warning line, nowhere
#    near the 50% that rejects.
#
# Revenue is precomputed because tools.py has no multiplication: without it,
# "total revenue per country" could only ever be cannot_answer. It is computed
# from the TRUE quantity, so the data stays internally consistent even where
# the quantity text is corrupt — which is what a half-mangled export looks
# like.

UNIQUE_ROWS = 1305
DUPLICATE_ROWS = 195  # 195 / 1500 = 13%
# 4% of the UNIQUE rows. The duplicates can copy a bad row, so the final
# convertible share lands a little under 96% — still clear of 0.95, and the
# script prints the real figure rather than the intended one.
BAD_QUANTITY_SHARE = 0.03
MISSING_PHONE_SHARE = 0.75

ORDER_COLUMNS = [
    "OrderID",
    "OrderDate",
    "Product",
    "Category",
    "quantity",
    "Price",
    "Revenue",
    "Country",
    "customer_phone",
]

# (product, category, unit price)
CATALOGUE = [
    ("Laptop", "Electronics", 1200.00),
    ("Monitor", "Electronics", 310.00),
    ("Tablet", "Electronics", 450.00),
    ("Mouse", "Accessories", 25.50),
    ("Keyboard", "Accessories", 45.00),
    ("Headset", "Accessories", 89.99),
    ("Webcam", "Accessories", 65.00),
    ("Docking Station", "Accessories", 145.00),
]

COUNTRIES = ["Germany", "France", "Spain", "Italy", "Netherlands", "Belgium"]

# Words that do not parse as numbers. Spread thinly on purpose: see note 2.
BAD_QUANTITIES = ["twelve", "n/a", "two", "unknown", "TBC"]

MONTHS = [(year, month) for year in (2023, 2024) for month in range(1, 13)]


def write_orders(path):
    """Phones are assigned BEFORE duplicating, which is the whole trick.

    A first version duplicated the base rows and then filled a random phone
    per row, so each "duplicate" got a different phone and was not a
    duplicate at all — `df.duplicated()` found none and the 13% warning never
    fired. The fixture looked right and tested nothing.
    """
    rng = random.Random(SEED)

    # Spread the unique rows over all 24 months, so every month has data and
    # no month is empty for a "per month" question.
    per_month, extra = divmod(UNIQUE_ROWS, len(MONTHS))
    counts = [per_month + (1 if index < extra else 0) for index in range(len(MONTHS))]

    rows = []
    order_id = 10001
    for (year, month), count in zip(MONTHS, counts):
        first = date(year, month, 1)
        days_in_month = ((first + timedelta(days=31)).replace(day=1) - first).days
        for _ in range(count):
            product, category, base_price = CATALOGUE[rng.randrange(len(CATALOGUE))]
            day = rng.randrange(1, days_in_month + 1)
            quantity = rng.randint(1, 25)
            # A little price drift, so averages are not suspiciously round.
            price = round(base_price * rng.uniform(0.95, 1.08), 2)
            rows.append(
                {
                    "OrderID": order_id,
                    "OrderDate": date(year, month, day).isoformat(),
                    "Product": product,
                    "Category": category,
                    "quantity": quantity,
                    "Price": price,
                    "Revenue": round(price * quantity, 2),
                    "Country": COUNTRIES[rng.randrange(len(COUNTRIES))],
                }
            )
            order_id += 1

    total = UNIQUE_ROWS + DUPLICATE_ROWS

    # quantity as text: mostly digits, some padded, 4% unparseable words.
    bad_count = round(total * BAD_QUANTITY_SHARE)
    bad_indices = set(rng.sample(range(UNIQUE_ROWS), bad_count))
    for index, row in enumerate(rows):
        if index in bad_indices:
            row["quantity"] = BAD_QUANTITIES[index % len(BAD_QUANTITIES)]
        elif index % 7 == 0:
            row["quantity"] = f" {row['quantity']} "  # whitespace padding
        else:
            row["quantity"] = str(row["quantity"])

    # ~75% of phones missing, chosen by count so the ratio is exact. The rows
    # that will be duplicated are excluded, so copying one cannot move it.
    duplicate_indices = rng.sample(range(UNIQUE_ROWS), DUPLICATE_ROWS)
    present_count = total - round(total * MISSING_PHONE_SHARE)
    candidates = [i for i in range(UNIQUE_ROWS) if i not in set(duplicate_indices)]
    present = set(rng.sample(candidates, present_count))

    for index, row in enumerate(rows):
        row["customer_phone"] = (
            f"+49-30-{rng.randint(1000000, 9999999)}" if index in present else ""
        )

    complete = rows + [dict(rows[i]) for i in duplicate_indices]

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ORDER_COLUMNS)
        writer.writeheader()
        writer.writerows(complete)

    return len(complete), total - present_count, bad_count


# ---------------------------------------------------------------------------
# customers.csv — the clean control
# ---------------------------------------------------------------------------
#
# Left completely clean on purpose. With orders.csv dirty, something has to
# still exercise the "no warnings at all" path, or a regression that made
# every upload warn would look entirely normal.

CUSTOMER_COLUMNS = [
    "CustomerID",
    "CustomerName",
    "Country",
    "SignupDate",
    "Age",
    "TotalSpent",
    "Segment",
]

CUSTOMER_ROWS = [
    ("C001", "Acme Industrial", "Germany", "2023-02-14", 41, 18400.00, "Enterprise"),
    ("C002", "Blue Harbour Ltd", "France", "2023-03-02", 35, 7250.50, "Mid-Market"),
    ("C003", "Cedar Analytics", "Spain", "2023-04-19", 29, 3120.00, "SMB"),
    ("C004", "Delta Freight", "Germany", "2023-05-07", 52, 22850.75, "Enterprise"),
    ("C005", "Evergreen Foods", "Italy", "2023-06-23", 44, 5600.00, "Mid-Market"),
    ("C006", "Fjord Systems", "Netherlands", "2023-07-11", 38, 9900.00, "Mid-Market"),
    ("C007", "Granite Partners", "Germany", "2023-08-05", 47, 31200.00, "Enterprise"),
    ("C008", "Harbour Lights", "France", "2023-09-17", 31, 2480.00, "SMB"),
    ("C009", "Ironwood Supply", "Spain", "2023-10-02", 55, 14300.25, "Enterprise"),
    ("C010", "Juniper Retail", "Italy", "2023-11-21", 27, 1950.00, "SMB"),
    ("C011", "Kestrel Media", "Germany", "2024-01-09", 33, 6700.00, "Mid-Market"),
    ("C012", "Lantern Health", "Netherlands", "2024-02-13", 49, 17450.00, "Enterprise"),
    ("C013", "Meridian Labs", "France", "2024-03-04", 36, 4200.00, "SMB"),
    ("C014", "Northgate Energy", "Germany", "2024-04-18", 58, 28900.50, "Enterprise"),
    ("C015", "Orchard Textiles", "Spain", "2024-05-26", 42, 8150.00, "Mid-Market"),
]


def write_customers(path):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CUSTOMER_COLUMNS)
        writer.writerows(CUSTOMER_ROWS)
    return len(CUSTOMER_ROWS)


# ---------------------------------------------------------------------------
# bad.csv — must be REJECTED
# ---------------------------------------------------------------------------
#
# The four data columns are each 55% missing while RecordID is always present,
# so the mean of the per-column ratios is (0 + 4 x 0.55) / 5 = 0.44, above
# MISSING_DATASET_THRESHOLD of 0.40.
#
# The arithmetic needs care. A first version blanked exactly half of each data
# column, giving 0.40 exactly — and the check is `>`, not `>=`, so the file
# was ACCEPTED and the fixture did the opposite of its job.
#
# No column reaches 70%, so nothing is merely excluded; and RecordID stays
# populated so the mostly-empty rows are not duplicates of each other, which
# would trip a second rule and muddle what this fixture demonstrates.

BAD_COLUMNS = ["RecordID", "Region", "Units", "Revenue", "Owner"]


def write_bad(path):
    rows = []
    # 11 of 20 = 55% per data column, taken from the top so the pattern is
    # obvious on sight rather than depending on the seed.
    blank_rows = set(range(11))
    for index in range(20):
        blank = index in blank_rows
        rows.append(
            [
                index + 1,
                "" if blank else ["North", "South", "East", "West"][index % 4],
                "" if blank else (index + 1) * 3,
                "" if blank else round((index + 1) * 12.5, 2),
                "" if blank else f"owner-{index + 1}",
            ]
        )

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(BAD_COLUMNS)
        writer.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    total, missing, bad = write_orders(HERE / "orders.csv")

    # Read back and report the ACTUAL convertible share, since duplicating a
    # bad row changes it.
    import csv as _csv

    with open(HERE / "orders.csv", encoding="utf-8") as handle:
        values = [row["quantity"] for row in _csv.DictReader(handle)]

    def _numeric(value):
        try:
            float(value.strip())
            return True
        except ValueError:
            return False

    convertible = sum(1 for v in values if _numeric(v)) / len(values)
    print(
        f"orders.csv    {total} rows over {len(MONTHS)} months, "
        f"{len(CATALOGUE)} products, {len(COUNTRIES)} countries"
    )
    print(
        f"              {missing} phones missing ({missing / total:.0%}), "
        f"{DUPLICATE_ROWS} duplicates ({DUPLICATE_ROWS / total:.0%}), "
        f"{len(values) - sum(1 for v in values if _numeric(v))} unparseable "
        f"quantities ({convertible:.1%} convertible, threshold 95%)"
    )

    count = write_customers(HERE / "customers.csv")
    print(f"customers.csv {count} rows, clean")

    count = write_bad(HERE / "bad.csv")
    print(
        f"bad.csv       {count} rows, 4 columns 55% missing "
        f"-> 44% overall (rejected: limit is 40%)"
    )
    print(f"\nseed {SEED} — output is byte-identical on every run")
