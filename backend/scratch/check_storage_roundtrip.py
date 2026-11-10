"""Live round-trip against Neon Object Storage, including dtype fidelity.

Run from backend/:  python scratch/check_storage_roundtrip.py

The unit tests in tests/test_dataframe_store.py use a dict-backed fake client,
which cannot prove that Neon itself round-trips a Parquet file or that dtypes
survive a real PutObject/GetObject. This script does, against the live bucket.

It writes five throwaway objects and deletes them again. Note that Neon's
delete is a soft delete and does not reclaim storage, so re-running this is
not entirely free in space.
"""
import sys, uuid
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
from app.services import dataframe_store as store

ds = uuid.uuid4()
original = pd.DataFrame({
    "Product": ["Laptop", "Mouse", "Keyboard", None],
    "Quantity": pd.Series([10, 5, 7, 3], dtype="int64"),
    "Price": pd.Series([1000.5, 25.0, np.nan, 50.25], dtype="float64"),
    "InStock": pd.Series([True, False, True, False], dtype="bool"),
    "order_date": pd.to_datetime(["2024-01-01", "2024-02-15", "2024-03-30", None]),
})

print("original dtypes:")
for c, d in original.dtypes.items():
    print(f"   {c:12} {d}")

key, size = store.save(ds, original)
print(f"\nsaved: key={key} bytes={size}")
assert size > 0

store.clear_cache()
print("cache cleared ->", store.cache_info())

loaded = store.load(key)
print("\nloaded dtypes:")
for c, d in loaded.dtypes.items():
    print(f"   {c:12} {d}")

print("\ndtypes identical       :", original.dtypes.equals(loaded.dtypes))
print("values identical       :", original.equals(loaded))
print("NaN/None preserved     :", loaded["Price"].isna().sum() == 1, loaded["Product"].isna().sum() == 1)
print("NaT preserved          :", loaded["order_date"].isna().sum() == 1)
print("no phantom index column:", "__index_level_0__" not in loaded.columns)
assert original.dtypes.equals(loaded.dtypes), "DTYPES CHANGED - the whole reason for Parquet"
assert original.equals(loaded), "values changed"

# cache behaviour
print("\n--- cache ---")
store.clear_cache()
first = store.load(key)
print("after 1st load:", store.cache_info()["size"], "entry")
second = store.load(key)
print("2nd load is the same object (no re-parse):", first is second)

# eviction at maxsize 3
store.clear_cache()
keys = []
for i in range(4):
    k, _ = store.save(uuid.uuid4(), pd.DataFrame({"n": [i]}))
    keys.append(k)
info = store.cache_info()
print("after saving 4 frames, cache size:", info["size"], "maxsize:", info["maxsize"])
print("oldest evicted:", keys[0] not in info["keys"])
print("newest retained:", keys[-1] in info["keys"])

# exists / delete / missing-object error
print("\n--- delete and the missing-object path ---")
print("exists before delete:", store.exists(key))
print("delete returned     :", store.delete(key))
try:
    store.clear_cache()
    store.load(key)
    print("load after delete   : STILL READABLE (Neon soft delete)")
except store.ObjectMissing as e:
    print("load after delete   : ObjectMissing raised ->", str(e)[:70])

try:
    store.load("datasets/definitely-not-a-real-object.parquet")
    print("missing object      : NO ERROR (unexpected)")
except store.ObjectMissing:
    print("missing object      : ObjectMissing raised, as designed")

# clean up the throwaway objects
for k in keys:
    store.delete(k)
print("\ncleaned up", len(keys), "test objects")
print("ROUND TRIP OK")
