"""Assign draft job families from titles and emit human-review tables."""

import itertools
import re

import pandas as pd

from common import require_file, write_csv
from config import PROFILE_DIR, RESOURCE_DIR, STEP_02_DIR, STEP_03_DIR

STATE_CODES = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
STATE_RE = r"\b(?:" + "|".join(STATE_CODES) + r")\b"
REMOVE_PARENS = re.compile(r"\([^)]*(?:\bremote\b|" + STATE_RE + r")[^)]*\)", re.I)
SYNONYMS = [
    (r"\bfront\s+end\b", "frontend"), (r"\bback\s+end\b", "backend"),
    (r"\bfull\s+stack\b", "fullstack"), (r"\bsales\s+force\b", "salesforce"),
    (r"\bquality\s+assurance\b", "qa"), (r"\bsite\s+reliability\b", "sre"),
    (r"\bmachine\s+learning\b", "ml"), (r"\bartificial\s+intelligence\b", "ai"),
]


def normalize_title(title: str) -> str:
    value = str(title).lower().replace("&", " and ")
    value = REMOVE_PARENS.sub(" ", value)
    value = re.sub(r"\b(security clearance|clearance required|with clearance|cleared|ts/sci|top secret|secret clearance|polygraph)\b", " ", value)
    value = re.sub(r"\s+-\s*location\b.*$|,\s*location open\b.*$", " ", value)
    for pattern, replacement in SYNONYMS:
        value = re.sub(pattern, replacement, value)
    value = re.sub(r"[^a-z0-9+#./]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def seniority_from_title(title: str) -> str:
    value = str(title).lower()
    if re.search(r"\b(lead|principal|staff|director|head of|manager)\b", value):
        return "lead"
    if re.search(r"\b(senior|sr\.?|iii|iv)\b", value):
        return "senior"
    if re.search(r"\b(junior|jr\.?|entry|intern|associate)\b", value) or re.search(r"\bi\s*$", value):
        return "junior"
    if re.search(r"\b(ii|mid)\b", value):
        return "mid"
    return "unspecified"


def main() -> None:
    source = require_file(STEP_02_DIR / "jobs_filtered.csv", ["id", "title", "desc_hash", "search_family"])
    rules_path = RESOURCE_DIR / "title_family_rules.csv"
    rules = require_file(rules_path, ["precedence", "family", "pattern", "is_non_it_hint"])
    rules["precedence"] = pd.to_numeric(rules.precedence, errors="raise")
    compiled = []
    for row in rules.sort_values("precedence").to_dict("records"):
        compiled.append({**row, "regex": re.compile(row["pattern"], re.I)})

    result = source.copy()
    result["title_norm"] = result.title.map(normalize_title)
    families, hits, conflicts, notes, seniority = [], [], [], [], []
    for raw_title, title_norm in zip(result.title, result.title_norm):
        matched = [rule for rule in compiled if rule["regex"].search(title_norm)]
        non_it = next((rule for rule in matched if str(rule["is_non_it_hint"]).strip() == "1"), None)
        if non_it:
            families.append("other")
            hits.append("other")
            conflicts.append(False)
            notes.append("non_it_hint")
        elif not matched:
            families.append("other")
            hits.append("")
            conflicts.append(False)
            notes.append("unmatched")
        else:
            matched = sorted(matched, key=lambda rule: int(rule["precedence"]))
            found = list(dict.fromkeys(rule["family"] for rule in matched))
            families.append(found[0])
            hits.append(";".join(found))
            conflicts.append(len(found) > 1)
            notes.append("precedence_rule" if len(found) > 1 else "matched")
        seniority.append(seniority_from_title(raw_title))

    result["job_family"] = families
    result["family_rule_hits"] = hits
    result["family_conflict"] = conflicts
    result["family_note"] = notes
    result["seniority_from_title"] = seniority
    write_csv(result, STEP_03_DIR / "jobs_family.csv")

    family_counts = result.groupby("job_family").agg(
        listings=("id", "nunique"), description_groups=("desc_hash", "nunique")
    ).reset_index()
    write_csv(family_counts, STEP_03_DIR / "family_counts.csv")

    unmatched = result.loc[result.job_family.eq("other")].groupby(["title_norm", "family_note"], dropna=False).agg(
        count=("id", "size"), example_title=("title", "first")
    ).reset_index().sort_values("count", ascending=False).head(100)
    write_csv(unmatched, STEP_03_DIR / "family_review_unmatched.csv")

    conflict_rows = result.loc[result.family_conflict, ["id", "title", "title_norm", "family_rule_hits", "job_family"]]
    write_csv(conflict_rows, STEP_03_DIR / "family_review_conflicts.csv")
    pair_counts = {}
    for value in conflict_rows.family_rule_hits:
        pair_counts_for_title = list(itertools.combinations(sorted(set(str(value).split(";"))), 2))
        for pair in pair_counts_for_title:
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
    pair_table = pd.DataFrame([
        {"family_a": pair[0], "family_b": pair[1], "count": count}
        for pair, count in sorted(pair_counts.items(), key=lambda item: (-item[1], item[0]))
    ], columns=["family_a", "family_b", "count"])
    write_csv(pair_table, STEP_03_DIR / "family_conflict_pairs.csv")

    terms = require_file(PROFILE_DIR / "job_search_terms.csv", ["id", "search_family"])
    terms = terms[["id", "search_family"]].drop_duplicates()
    cross = terms.merge(result[["id", "job_family"]], on="id", how="inner").drop_duplicates()
    crosstab = cross.groupby(["search_family", "job_family"]).size().rename("count").reset_index()
    crosstab["row_share_pct"] = crosstab["count"] / crosstab.groupby("search_family")["count"].transform("sum") * 100
    write_csv(crosstab, STEP_03_DIR / "family_crosstab_search_vs_title.csv")

    other_share = result.job_family.eq("other").mean() * 100
    print(f"Title-family rows: {len(result)}; other={other_share:.1f}%; conflicts={int(result.family_conflict.sum())}.")
    print(f"Family counts written to {STEP_03_DIR / 'family_counts.csv'}; review unmatched/conflicts before analysis.")
    print(family_counts.sort_values("description_groups", ascending=False).to_string(index=False))
    if not pair_table.empty:
        print("Top conflict pairs:")
        print(pair_table.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
