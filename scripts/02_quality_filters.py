"""Apply certain structural filters and preserve uncertain quality cases for review."""

import re

import numpy as np
import pandas as pd

from common import record_attrition, require_file, write_csv
from config import DATE_PROXY_DAYS, ENGLISH_MIN_STOPWORD_SHARE, ENGLISH_MIN_TOKENS, PROFILE_DIR, STEP_02_DIR

STOPWORDS = set("the and of to a in for with is on as be are or by an at that will this you we our your from have has can".split())
WORD_RE = re.compile(r"[a-z']+")


def stopword_share(text: str) -> tuple[int, float]:
    tokens = WORD_RE.findall(str(text).lower())
    return len(tokens), (sum(token in STOPWORDS for token in tokens) / len(tokens) if tokens else 0.0)


def main() -> None:
    source = require_file(PROFILE_DIR / "jobs_slim.csv", [
        "id", "title", "descriptionText", "contributor", "source_file", "postedAt", "applicantsCount", "employmentType",
    ])
    rows_in = len(source)
    source["n_words"] = source["descriptionText"].astype(str).str.split().str.len()
    source["_missing_required"] = source["title"].str.strip().eq("") | source["descriptionText"].str.strip().eq("")
    missing_count = int(source["_missing_required"].sum())
    stage1 = source.loc[~source["_missing_required"]].copy()
    record_attrition("02.1_missing_title_or_description", rows_in, len(stage1), "Removed rows with an empty title or description.")

    short_count = int(stage1["n_words"].lt(50).sum())
    filtered = stage1.loc[stage1["n_words"].ge(50)].copy()
    record_attrition("02.2_description_under_50_words", len(stage1), len(filtered), "Removed descriptions shorter than 50 whitespace-delimited words.")

    # Language and date checks are flags, not automatic removals: run-date metadata is absent.
    lang_metrics = source["descriptionText"].map(stopword_share)
    source["english_token_count"] = [item[0] for item in lang_metrics]
    source["english_stopword_share"] = [round(item[1], 4) for item in lang_metrics]
    source["likely_non_english"] = (
        source["english_token_count"].lt(ENGLISH_MIN_TOKENS)
        | source["english_stopword_share"].lt(ENGLISH_MIN_STOPWORD_SHARE)
    )

    profile = require_file(PROFILE_DIR / "profile_by_file.csv", ["contributor", "posted_to"])
    proxy = profile.assign(_date=pd.to_datetime(profile.posted_to, errors="coerce")).groupby("contributor")["_date"].max()
    source["_posted_at"] = pd.to_datetime(source.postedAt, errors="coerce")
    source["date_proxy_days_behind"] = source.apply(
        lambda row: (proxy.get(row["contributor"]) - row["_posted_at"]).days
        if pd.notna(proxy.get(row["contributor"])) and pd.notna(row["_posted_at"]) else np.nan,
        axis=1,
    )
    source["outside_31_day_proxy"] = source["date_proxy_days_behind"].gt(DATE_PROXY_DAYS)

    q1, q3 = filtered.n_words.quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr

    source["employment_odd"] = source.employmentType.str.strip().str.lower().isin({"volunteer", "other"})
    source["length_outlier"] = source.n_words.lt(lower) | source.n_words.gt(upper)
    source["short_description"] = source.n_words.between(50, 99)

    flag_rows = []
    for row in source.to_dict("records"):
        flags = []
        for name in ["_missing_required", "outside_31_day_proxy", "employment_odd", "length_outlier", "short_description"]:
            if bool(row.get(name, False)):
                flags.append(name.removeprefix("_"))
        if flags:
            flag_rows.append({
                "id": row["id"], "title": row["title"], "contributor": row["contributor"],
                "source_file": row["source_file"], "flags": ";".join(flags),
                "english_token_count": row["english_token_count"],
                "english_stopword_share": row["english_stopword_share"],
                "date_proxy_days_behind": row["date_proxy_days_behind"],
                "retained_after_structural_filters": not bool(row["_missing_required"]) and int(row["n_words"]) >= 50,
            })

    write_csv(filtered.drop(columns=["_missing_required"]), STEP_02_DIR / "jobs_filtered.csv")
    quality_flags = pd.DataFrame(flag_rows)
    descriptions = filtered[["id", "descriptionText"]].drop_duplicates("id")
    quality_flags_review = quality_flags.merge(descriptions, on="id", how="left", validate="many_to_one")
    quality_flags_review["description_found_in_jobs_filtered"] = quality_flags_review.descriptionText.notna().map({True: "yes", False: "no"})
    quality_flags_review["descriptionText"] = quality_flags_review.descriptionText.fillna("")
    write_csv(quality_flags, STEP_02_DIR / "quality_flags.csv")
    write_csv(quality_flags_review, STEP_02_DIR / "quality_flags_with_descriptions.csv")
    non_english = source.loc[source.likely_non_english, ["id", "title", "contributor", "source_file", "english_token_count", "english_stopword_share"]]
    write_csv(non_english, STEP_02_DIR / "non_english_review.csv")
    date_review = source.loc[source.outside_31_day_proxy, ["id", "title", "contributor", "source_file", "postedAt", "date_proxy_days_behind"]]
    write_csv(date_review, STEP_02_DIR / "date_proxy_review.csv")

    missing_lines = []
    for field in ["companyName", "location", "postedAt", "employmentType", "seniorityLevel", "industries", "salary"]:
        count = int(source[field].astype(str).str.strip().eq("").sum()) if field in source else len(source)
        missing_lines.append(f"Missing {field}: {count}/{len(source)}")
    summary = [
        f"Unique-ID listings before filters: {rows_in}",
        f"Rows after structural filters: {len(filtered)}",
        f"Removed empty title/description: {missing_count}",
        f"Removed under-50-word descriptions after empty-text filter: {short_count}",
        f"Descriptions with 50-99 words retained and flagged: {int(source.n_words.between(50, 99).sum())}",
        f"Language-heuristic candidates listed separately; excluded from quality_flags.csv: {len(non_english)}",
        f"Rows older than 31-day contributor posted-date proxy, flagged only: {len(date_review)}",
        f"Median description length in words: {source.n_words.median():.1f}",
        "",
        *missing_lines,
        "",
        "The contributor latest-posted-date value is a proxy, not an actor collection date. No date-based rows were removed.",
        "The URL's f_TPR parameter and returned location values should be checked separately before final scope claims.",
    ]
    STEP_02_DIR.mkdir(parents=True, exist_ok=True)
    (STEP_02_DIR / "data_quality_summary.txt").write_text("\n".join(summary), encoding="utf-8")

    print(f"Input unique-ID listings: {rows_in}")
    print(f"Removed empty title/description: {missing_count}; removed under 50 words: {short_count}")
    print(f"Output rows: {len(filtered)}; language-heuristic candidates listed separately and excluded from quality flags: {len(non_english)}")
    print(f"Date-proxy candidates flagged (not removed): {len(date_review)}; description word-count IQR=[{lower:.1f}, {upper:.1f}]")


if __name__ == "__main__":
    main()
