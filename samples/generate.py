"""Regenerate the sample CSVs. Deterministic.

Run from the repo root:  python samples/generate.py

    orders.csv     dirty on purpose, but still ACCEPTED
    customers.csv  clean, the control case
    bad.csv        dirty enough to be REJECTED

Everything random is drawn from ``SEED``, so the files are byte-identical on
every run. That matters more than it looks: the expected answers in the
verification runs (and in docs/PLAN.md) are specific numbers, and a sample
file that quietly changed would turn a correct answer into a failing check
with no code change to blame.

Why orders.csv is dirty rather than clean: a clean sample only ever exercises
the happy path, so the preprocessing report, the excluded-column handling and
the type-conversion notice are never seen until a real user finds them. Each
flaw below is aimed at one specific code path, and the thresholds in
validation.py are what decide how far each one can go.
"""

import csv
import pathlib
import random

SEED = 20260111
HERE = pathlib.Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# orders.csv — dirty, but inside every rejection threshold
# ---------------------------------------------------------------------------
#
# Thresholds this file is deliberately steering between (validation.py):
#
#   MISSING_COLUMN_THRESHOLD   0.70  a column above this is EXCLUDED
#   MISSING_DATASET_THRESHOLD  0.40  a dataset above this is REJECTED
#   DUPLICATE_WARNING_THRESHOLD 0.10 above this: a warning
#   DUPLICATE_REJECT_THRESHOLD  0.50 above this: rejected
#   TYPE_CONVERSION_THRESHOLD  0.95  below this: the column is NOT converted
#
# 1. customer_phone is ~75% missing: ABOVE the column threshold, so it is
#    excluded with a reason, and the agent is told why rather than silently
#    losing a column. One column at 75% of eight keeps the dataset average
#    near 9%, far below the 40% that would reject the whole file.
#
# 2. quantity arrives as TEXT. Some values are whitespace-padded and exactly
#    ONE is a word ("twelve"). That is the sharp bit: 22 of 23 values parse,
#    which is 95.6% and just clears the 95% conversion threshold, so the
#    column IS converted to numeric and the unparseable row becomes NaN. A
#    second bad value would drop it to 91% and the column would stay text —
#    at which point summing it would concatenate strings and the answer to
#    "highest total quantity" would be silently wrong.
#
# 3. Three duplicate rows out of 23 is 13%: above the 10% warning line,
#    nowhere near the 50% that rejects.

ORDER_COLUMNS = [
    "OrderID",
    "OrderDate",
    "Product",
    "Category",
    "quantity",
    "Price",
    "Country",
    "customer_phone",
]

ORDER_ROWS = [
    (1001, "2024-01-05", "Laptop", "Electronics", "3", 1200.00, "Germany"),
    (1002, "2024-01-07", "Mouse", "Accessories", "10", 25.50, "France"),
    (1003, "2024-01-11", "Keyboard", "Accessories", " 7 ", 45.00, "Spain"),
    (1004, "2024-01-15", "Laptop", "Electronics", "2", 1200.00, "Germany"),
    (1005, "2024-01-19", "Monitor", "Electronics", "4", 310.00, "Italy"),
    (1006, "2024-02-02", "Mouse", "Accessories", "15", 25.50, "Germany"),
    (1007, "2024-02-08", "Headset", "Accessories", "6", 89.99, "France"),
    (1008, "2024-02-14", "Laptop", "Electronics", "1", 1250.00, "Netherlands"),
    (1009, "2024-02-21", "Monitor", "Electronics", "5", 299.00, "Spain"),
    (1010, "2024-03-03", "Keyboard", "Accessories", "12", 42.00, "Germany"),
    (1011, "2024-03-09", "Webcam", "Accessories", "8", 65.00, "Italy"),
    (1012, "2024-03-16", "Laptop", "Electronics", "2", 1180.00, "France"),
    (1013, "2024-03-22", "Mouse", "Accessories", "20", 24.00, "Spain"),
    (1014, "2024-04-01", "Monitor", "Electronics", " 3", 320.00, "Germany"),
    (1015, "2024-04-08", "Headset", "Accessories", "9", 85.00, "Netherlands"),
    # The one value that cannot be parsed. Keep it to exactly one.
    (1016, "2024-04-15", "Docking Station", "Accessories", "twelve", 145.00, "Germany"),
    (1017, "2024-04-23", "Laptop", "Electronics", "4", 1210.00, "Italy"),
    (1018, "2024-05-02", "Webcam", "Accessories", "11", 62.50, "France"),
    (1019, "2024-05-11", "Keyboard", "Accessories", "6 ", 48.00, "Netherlands"),
    (1020, "2024-05-18", "Monitor", "Electronics", "2", 305.00, "Spain"),
]

# Rows repeated verbatim, by index into ORDER_ROWS. Three of 23 = 13%.
DUPLICATE_INDICES = [1, 5, 11]


def write_orders(path):
    """Phones are assigned BEFORE duplicating, which is the whole trick.

    A first attempt duplicated the base rows and then filled phones per row.
    Because the phone is random, the "duplicates" each got a different phone
    and were not duplicates at all — `df.duplicated()` found none and the
    13% duplicate warning never fired. The fixture looked right and tested
    nothing. Duplicating complete rows is what makes them exact.

    The rows chosen to carry a phone also exclude the duplicated ones, so
    copying a row cannot change the missing-phone ratio.
    """
    rng = random.Random(SEED)

    total = len(ORDER_ROWS) + len(DUPLICATE_INDICES)
    present_count = total - round(total * 0.75)

    candidates = [i for i in range(len(ORDER_ROWS)) if i not in DUPLICATE_INDICES]
    present_indices = set(rng.sample(candidates, present_count))

    complete = []
    for index, row in enumerate(ORDER_ROWS):
        phone = ""
        if index in present_indices:
            phone = f"+49-30-{rng.randint(1000000, 9999999)}"
        complete.append(list(row) + [phone])

    rows = complete + [list(complete[i]) for i in DUPLICATE_INDICES]

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(ORDER_COLUMNS)
        writer.writerows(rows)

    return len(rows), total - present_count


# ---------------------------------------------------------------------------
# customers.csv — the clean control
# ---------------------------------------------------------------------------
#
# Left completely clean on purpose. With orders.csv now dirty, something has
# to still exercise the "no warnings at all" path, or a regression that makes
# every upload produce a warning would look normal.

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
# The arithmetic needs care. A first attempt blanked exactly half of each data
# column, giving (0 + 4 x 0.50) / 5 = 0.40 exactly — and the check is `>`, not
# `>=`, so the file was ACCEPTED. 55% is chosen to clear the threshold with
# margin rather than to sit on it.
#
# Two other things this fixture is steering around:
#
# - No column reaches 70%, so no column is excluded. Had one column carried
#   all the missingness it would be dropped and the file accepted, which is a
#   different code path and not the one this fixture is for.
# - RecordID stays populated so that no two rows are identical. Blanking it
#   too would make the empty rows duplicates of each other and the file would
#   trip the duplicate rule as well, muddling what the fixture demonstrates.
#
# Note that overall_missing_ratio is the mean of the per-column means, not the
# fraction of missing cells (see tests/test_validation.py).

BAD_COLUMNS = ["RecordID", "Region", "Units", "Revenue", "Owner"]


def write_bad(path):
    rows = []
    # 11 of 20 = 55% per data column. Taken from the top so the pattern is
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
    total, missing = write_orders(HERE / "orders.csv")
    print(f"orders.csv    {total} rows, {missing} phones missing "
          f"({missing / total:.0%}), 3 duplicates, quantity as text")

    count = write_customers(HERE / "customers.csv")
    print(f"customers.csv {count} rows, clean")

    count = write_bad(HERE / "bad.csv")
    print(f"bad.csv       {count} rows, 4 columns 55% missing "
          f"-> 44% overall (rejected: limit is 40%)")
    print(f"\nseed {SEED} — output is byte-identical on every run")
