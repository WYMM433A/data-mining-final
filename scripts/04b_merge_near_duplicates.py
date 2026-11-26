"""Merge confirmed true-duplicate near-duplicate postings (Step 4b).

Of the 373 near-duplicate pairs (cosine >= 0.95) flagged in Step 4 but never merged,
only the 74 pairs that share both the same normalized title AND the same location are
true duplicates (same posting, scraped/posted twice). The other 299 are either the same
requisition posted to multiple office locations, or genuinely different jobs that reuse
a company's boilerplate template - both are left untouched.

Rebuilds description_group_id for the 74 confirmed cases, then regenerates jobs_desc.csv
(one representative row per group) using the same selection rule as the original script
(most recent posting, then longest description, then lowest id).
"""

import pandas as pd

from common import write_csv
from config import STEP_04_DIR

EDGES_PATH = STEP_04_DIR / "near_duplicate_edges.csv"
LISTING_PATH = STEP_04_DIR / "jobs_listing.csv"
DESC_PATH = STEP_04_DIR / "jobs_desc.csv"


def find(parent: dict, x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def union(parent: dict, a, b):
    ra, rb = find(parent, a), find(parent, b)
    if ra != rb:
        lo, hi = sorted((ra, rb))
        parent[hi] = lo


def main() -> None:
    edges = pd.read_csv(EDGES_PATH)
    listing = pd.read_csv(LISTING_PATH, low_memory=False)
    listing_idx = listing.set_index("id")

    true_dupe_group_pairs = []
    for row in edges.itertuples():
        a, b = listing_idx.loc[row.job_id_a], listing_idx.loc[row.job_id_b]
        if a.title_norm == b.title_norm and a.location == b.location:
            true_dupe_group_pairs.append((a.description_group_id, b.description_group_id))

    parent = {gid: gid for gid in listing.description_group_id.unique()}
    for ga, gb in true_dupe_group_pairs:
        union(parent, ga, gb)
    remap = {gid: find(parent, gid) for gid in parent}
    changed = sum(1 for gid, new in remap.items() if gid != new)
    print(f"Confirmed true-duplicate group pairs: {len(true_dupe_group_pairs)}")
    print(f"Description groups remapped to a merged representative: {changed}")

    listing["description_group_id"] = listing.description_group_id.map(remap)

    grouped = listing.groupby("description_group_id").agg(
        description_group_size=("id", "size"),
        n_distinct_titles_in_group=("title", "nunique"),
        n_distinct_families_in_group=("job_family", "nunique"),
    )
    listing = listing.drop(columns=["description_group_size", "n_distinct_titles_in_group",
                                     "n_distinct_families_in_group", "family_group_ambiguous"])
    listing = listing.join(grouped, on="description_group_id")
    listing["family_group_ambiguous"] = listing.n_distinct_families_in_group.gt(1)

    listing["_posted_sort"] = pd.to_datetime(listing.postedAt, errors="coerce")
    reps = listing.sort_values(
        ["description_group_id", "_posted_sort", "n_words", "id"],
        ascending=[True, False, False, True], kind="mergesort",
    ).drop_duplicates("description_group_id")
    desc = reps.drop(columns=["_posted_sort"])
    listing = listing.drop(columns=["_posted_sort"])

    write_csv(listing, LISTING_PATH)
    write_csv(desc, DESC_PATH)

    print(f"jobs_listing.csv: {len(listing)} rows (unchanged count, group ids updated)")
    print(f"jobs_desc.csv: {len(desc)} rows (was {listing.description_group_id.nunique() + changed}; "
          f"now {desc.description_group_id.nunique()} unique groups)")


if __name__ == "__main__":
    main()
