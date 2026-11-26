"""Build the collection log from the raw-file profile and search URLs."""

from urllib.parse import parse_qs, urlparse

import pandas as pd

from common import normalize_keyword, require_file, write_csv
from config import ACCEPTED_VARIANTS, PLANNED_KEYWORDS, PROFILE_DIR, RAW_DIR, STEP_01_DIR


def query_value(url: str, key: str) -> str:
    return parse_qs(urlparse(str(url)).query, keep_blank_values=True).get(key, [""])[0]


def main() -> None:
    profile_path = PROFILE_DIR / "profile_by_file.csv"
    profile = require_file(profile_path, [
        "contributor", "file", "search_family", "keyword_in_url", "location_in_url",
        "rows", "unique_ids", "posted_from", "posted_to",
    ])
    planned = {normalize_keyword(term): term for term in PLANNED_KEYWORDS}
    accepted = {normalize_keyword(term): (canonical, note) for term, (canonical, note) in ACCEPTED_VARIANTS.items()}
    proxy_by_contributor = (
        profile.assign(_posted_to=pd.to_datetime(profile["posted_to"], errors="coerce"))
        .groupby("contributor")["_posted_to"].max().dt.strftime("%Y-%m-%d").to_dict()
    )

    records = []
    for row in profile.to_dict("records"):
        raw_file = RAW_DIR / row["contributor"] / row["file"]
        if not raw_file.is_file():
            raise FileNotFoundError(f"Profile references missing raw file: {raw_file}")
        input_url = pd.read_csv(raw_file, usecols=["inputUrl"], dtype=str, keep_default_na=False, nrows=1)["inputUrl"].iloc[0]
        actual = row["keyword_in_url"].strip()
        normalized = normalize_keyword(actual)
        planned_keyword = planned.get(normalized, "")
        note = ""
        if "+" in actual and planned_keyword:
            status = "accepted_variant"
            note = "Accepted plus-encoded keyword variant; spot-check returned titles."
        elif normalized in accepted:
            planned_keyword, note = accepted[normalized]
            status = "accepted_variant"
        elif planned_keyword:
            status = "as_planned"
        else:
            status = "unmapped_review"
        filter_value = query_value(input_url, "f_TPR")
        date_filter = f"past month (f_TPR={filter_value})" if filter_value else "not recorded in URL"
        if "+" in row["location_in_url"]:
            note = "; ".join(filter(None, [note, "Location query contains a literal plus; verify US-location results."]))
        records.append({
            "contributor": row["contributor"],
            "file": row["file"],
            "search_family": row["search_family"],
            "search_term_used": actual,
            "planned_keyword": planned_keyword,
            "keyword_status": status,
            "location": row["location_in_url"],
            "date_filter": date_filter,
            "rows": int(row["rows"]),
            "unique_ids_in_file": int(row["unique_ids"]),
            "posted_from": row["posted_from"],
            "posted_to": row["posted_to"],
            "collection_date_proxy": proxy_by_contributor.get(row["contributor"], ""),
            "actor_name": "",
            "actor_version": "",
            "max_results_setting": "",
            "cost_usd": "",
            "notes": "; ".join(filter(None, [note, "Actual actor run date is not present in the exports; proxy is latest posted date for contributor.", "FILL BY HAND: actor, version, result limit, cost."])),
        })

    result = pd.DataFrame(records).sort_values(["contributor", "file"])
    if len(result) != 34:
        print(f"Review: expected 34 input files, found {len(result)}.")
    if result["search_family"].eq("").any():
        raise ValueError("One or more files have no search_family mapping.")
    write_csv(result, STEP_01_DIR / "collection_log.csv")
    print(f"Wrote {len(result)} collection-log rows; raw rows={result['rows'].astype(int).sum()}.")
    print("Accepted variants:")
    print(result.loc[result.keyword_status.eq("accepted_variant"), ["file", "search_term_used", "planned_keyword"]].to_string(index=False))
    if result.keyword_status.eq("unmapped_review").any():
        print("Unmapped search terms:")
        print(result.loc[result.keyword_status.eq("unmapped_review"), ["file", "search_term_used"]].to_string(index=False))


if __name__ == "__main__":
    main()
