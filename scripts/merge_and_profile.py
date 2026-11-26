"""
Merge the raw Apify CSVs (data/raw/<contributor>/*.csv), shrink them, and profile them.

Run from the project folder:
    python scripts/merge_and_profile.py
    python scripts/merge_and_profile.py data/raw outputs/00_source_profile

Raw files are only READ. Nothing in data/raw is changed.
Outputs (in out_profile/):
    jobs_slim.csv            one row per unique job ID (listing level), personal/heavy columns dropped, text normalised
    job_search_terms.csv     every (job ID, search term) pair, so no search provenance is lost
    description_groups.csv   groups of identical normalised descriptions (description-level view)
    profile_by_file.csv      one row per input file: rows, ids, keyword check, relevance, dates, top company share
    title_review.csv         top titles and sample NON-matching titles per file, for a human relevance check
    company_concentration.csv  top companies, listing level and description level
    profile_overall.txt      the headline numbers
    upload_pack.zip          the files above, zipped (small enough to share)
"""
import sys, re, hashlib, zipfile
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import datetime as dt
import pandas as pd

KEEP = ["id", "link", "title", "companyName", "location", "postedAt", "employmentType", "seniorityLevel",
        "industries", "salary", "applicantsCount", "descriptionText", "inputUrl"]
# NOT copied (personal or heavy): jobPoster*, descriptionHtml, applyUrl, company* address/logo/slogan/website/description,
# trackingId, refId, companyLinkedinUrl, companyEmployeesCount (add back to KEEP if you want company size)

PLANNED = ["Data Analyst", "Business Intelligence Analyst", "Business Intelligence Developer", "Reporting Analyst", "Analytics Engineer",
 "Data Scientist", "Machine Learning Engineer", "AI Engineer", "NLP Engineer", "Computer Vision Engineer",
 "Software Engineer", "Frontend Developer", "Backend Developer", "Full Stack Developer", "Mobile App Developer",
 "DevOps Engineer", "Cloud Engineer", "Site Reliability Engineer", "Platform Engineer", "Infrastructure Engineer",
 "Cybersecurity Analyst", "Security Engineer", "Network Engineer", "Information Security Analyst",
 "Data Engineer", "Database Administrator", "Database Developer", "Data Architect",
 "QA Engineer", "Automation Test Engineer", "Software Test Engineer",
 "ERP Consultant", "Salesforce Developer", "SAP Consultant"]
PLANNED_NORM = {re.sub(r"[^a-z0-9]+", " ", k.lower()).strip() for k in PLANNED}

FAMILY_BY_STEM = {}
for stems, fam in [
  (["ai_engineer","computer_vision_engineer","data_scientist","machine_learning_engineer","nlp_engineer"], "AI & Machine Learning"),
  (["cloud_engineer","devops_engineer","infrastructure_engineer","platform_engineer","site_reliability_engineer"], "Cloud, DevOps & Infrastructure"),
  (["sales_force_engineer","erp_consultant","sap_consultant"], "Enterprise Software & IT Systems"),
  (["cybersecurity_analyst","information_security_analyst","network_engineer","security_engineer"], "Cybersecurity & Networking"),
  (["data_architect","data_engineer","database_administrator","database_developer"], "Database & Data Infrastructure"),
  (["mobile_app_developer","back_end_developer","frontend_developer","full_stack_developer","software_engineer"], "Software Development & Engineering"),
  (["analytics_engineers","business_intelligence_analyst","business_intelligence_developer","data_analyst","reporting_analyst"], "Data & Business Intelligence"),
  (["quality_assurance_automation_engineer","quality_assurance_engineer","software_test_engineer"], "QA & Software Testing")]:
    for s in stems: FAMILY_BY_STEM[s] = fam

CHARS = {"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-", "\u2011": "-", "\u2010": "-",
         "\u202f": " ", "\u00a0": " ", "\u2009": " ", "\u200b": "", "\u200c": "", "\ufeff": "", "\u2022": "-", "\u2192": "->"}
TRANS = str.maketrans(CHARS)
def norm_text(s):
    s = str(s).translate(TRANS).replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[ \t]+", " ", s).strip()

def raw_param(url, name):
    m = re.search(r"[?&]" + name + r"=([^&]*)", str(url))
    return m.group(1) if m else ""

def param(url, name):
    # parse_qs already decodes URL form values. Calling unquote_plus again would
    # turn an encoded literal plus (%2B) into a space and hide the distinction.
    return parse_qs(urlparse(str(url)).query).get(name, [""])[0]

GENERIC = {"engineer", "engineers", "developer", "developers", "analyst", "analysts", "administrator", "consultant", "architect"}
SYN = [("front end", "frontend"), ("back end", "backend"), ("full stack", "fullstack"), ("sales force", "salesforce"),
       ("machine learning", "ml"), ("artificial intelligence", "ai"), ("quality assurance", "qa"), ("site reliability", "sre")]
def tokens(s):
    s = s.lower()
    for a, b in SYN: s = s.replace(a, b)
    return [t[:-1] if t.endswith("s") and len(t) > 4 else t for t in re.findall(r"[a-z0-9]+", s.lower())]
def title_match(title, kw):
    tt = set(tokens(title)); kt = tokens(kw)
    strict = all(t in tt for t in kt)
    loose = any(t in tt for t in kt if t not in GENERIC) or strict
    return strict, loose

def main(raw_root, out_dir):
    raw_root, out = Path(raw_root), Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    files = sorted(raw_root.rglob("*.csv"))
    if not files: sys.exit(f"No CSV files under {raw_root}")
    frames, prof, titles_rev = [], [], []
    for f in files:
        df = pd.read_csv(f, dtype=str, keep_default_na=False, usecols=lambda c: c in KEEP)
        stem = f.stem.lower()
        kw = param(df["inputUrl"].iloc[0], "keywords") if len(df) else ""
        loc = param(df["inputUrl"].iloc[0], "location") if len(df) else ""
        df["contributor"] = f.parent.name; df["source_file"] = f.name
        df["search_family"] = FAMILY_BY_STEM.get(stem, "UNMAPPED")
        df["search_term"] = df["inputUrl"].map(lambda u: param(u, "keywords"))
        df["file_modified"] = dt.date.fromtimestamp(f.stat().st_mtime).isoformat()
        sm = [title_match(t, kw) for t in df["title"]]
        df["_strict"] = [a for a, _ in sm]; df["_loose"] = [b for _, b in sm]
        frames.append(df)
        top_share = df["companyName"].value_counts(normalize=True).iloc[0] if len(df) else 0
        dates = pd.to_datetime(df["postedAt"], errors="coerce")
        prof.append({"contributor": f.parent.name, "file": f.name, "search_family": FAMILY_BY_STEM.get(stem, "UNMAPPED"),
            "keyword_in_url": kw, "location_in_url": loc,
            "keyword_is_planned": re.sub(r"[^a-z0-9]+", " ", kw.lower()).strip() in PLANNED_NORM,
            # Check decoded values: a plus sign in the URL may be encoded as %2B.
            "keyword_has_plus_or_typo": bool("+" in kw or re.search(r"(.)\1\1", kw)),
            "location_has_plus": bool("+" in loc),
            "rows": len(df), "unique_ids": df["id"].nunique(), "unique_titles": df["title"].nunique(),
            "title_has_all_keyword_words_pct": round(100 * df["_strict"].mean(), 1),
            "title_has_main_keyword_word_pct": round(100 * df["_loose"].mean(), 1),
            "top_company": df["companyName"].value_counts().index[0] if len(df) else "", "top_company_share_pct": round(100 * top_share, 1),
            "posted_from": dates.min().date() if dates.notna().any() else "", "posted_to": dates.max().date() if dates.notna().any() else "",
            "missing_description": int((df["descriptionText"].str.strip() == "").sum()),
            "median_words": int(df["descriptionText"].str.split().str.len().median()),
            "rows_with_odd_characters": int(df["descriptionText"].str.contains("[\u202f\u200b\u2011\u00a0]").sum())})
        tv = df["title"].value_counts().head(10)
        for t, n in tv.items(): titles_rev.append({"file": f.name, "keyword": kw, "kind": "top title", "title": t, "count": int(n)})
        for t in df.loc[~df["_loose"], "title"].drop_duplicates().head(15): titles_rev.append({"file": f.name, "keyword": kw, "kind": "NOT matching keyword (review)", "title": t, "count": ""})
    allr = pd.concat(frames, ignore_index=True)
    allr["id"] = allr["id"].str.strip()

    # search terms (provenance) keep EVERY pair
    terms = allr[["id", "search_term", "search_family", "contributor", "source_file", "file_modified"]].drop_duplicates()
    terms.to_csv(out / "job_search_terms.csv", index=False)

    # listing level: one row per job ID
    allr["link"] = allr["link"].str.split("?").str[0]
    for c in ["title", "companyName", "location", "descriptionText", "industries"]: allr[c] = allr[c].map(norm_text)
    allr["n_words"] = allr["descriptionText"].str.split().str.len()
    allr["desc_key"] = allr["companyName"].str.lower() + "|" + allr["descriptionText"].str.lower().str.replace(r"\s+", " ", regex=True)
    allr["desc_hash"] = allr["desc_key"].map(lambda s: hashlib.md5(s.encode("utf-8")).hexdigest()[:12])
    n_terms = allr.groupby("id")["search_term"].nunique()
    jobs = allr.drop_duplicates("id").drop(columns=["_strict", "_loose", "desc_key", "inputUrl", "search_term"]).copy()
    jobs["n_search_terms"] = jobs["id"].map(n_terms)
    jobs["description_group_size"] = jobs.groupby("desc_hash")["id"].transform("count")
    jobs["description_group_id"] = jobs["desc_hash"].rank(method="dense").astype(int)
    jobs.to_csv(out / "jobs_slim.csv", index=False)
    g = jobs.groupby("description_group_id").agg(company=("companyName", "first"), group_size=("id", "count"),
            example_title=("title", "first"), n_distinct_titles=("title", "nunique")).reset_index()
    g[g["group_size"] > 1].sort_values("group_size", ascending=False).to_csv(out / "description_groups.csv", index=False)

    pd.DataFrame(prof).to_csv(out / "profile_by_file.csv", index=False)
    pd.DataFrame(titles_rev).to_csv(out / "title_review.csv", index=False)
    rep = jobs.drop_duplicates("desc_hash")
    cc = pd.concat([jobs["companyName"].value_counts().head(25).rename("listings"),
                    rep["companyName"].value_counts().rename("unique_descriptions")], axis=1).sort_values("listings", ascending=False).head(25)
    cc["listing_share_pct"] = (100 * cc["listings"] / len(jobs)).round(1)
    cc["description_share_pct"] = (100 * cc["unique_descriptions"] / len(rep)).round(1)
    cc.rename_axis("company").reset_index().to_csv(out / "company_concentration.csv", index=False)

    lines = [f"Files: {len(files)}", f"Raw rows: {len(allr)}", f"Distinct job IDs (listing level): {len(jobs)}",
             f"IDs found by more than one search term: {(n_terms > 1).sum()}",
             f"Distinct descriptions (company + text): {rep.shape[0]}", f"Rows in repeated-description groups beyond the first: {len(jobs) - rep.shape[0]}",
             f"Companies: {jobs['companyName'].nunique()}  | top company share (listings): {cc['listing_share_pct'].iloc[0]}% ({cc.index[0]})",
             f"Posted range: {pd.to_datetime(jobs['postedAt'], errors='coerce').min().date()} to {pd.to_datetime(jobs['postedAt'], errors='coerce').max().date()}",
             f"Unmapped files: {sum(p['search_family']=='UNMAPPED' for p in prof)}",
             f"Files with keyword not in the planned list: {sum(not p['keyword_is_planned'] for p in prof)}",
             f"Files with a keyword typo or '+' flagged: {sum(p['keyword_has_plus_or_typo'] for p in prof)}",
             f"Files with '+' in the location: {sum(p['location_has_plus'] for p in prof)}"]
    (out / "profile_overall.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    with zipfile.ZipFile(out / "upload_pack.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for n in ["jobs_slim.csv", "job_search_terms.csv", "description_groups.csv", "profile_by_file.csv", "title_review.csv", "company_concentration.csv", "profile_overall.txt"]:
            z.write(out / n, n)
    print("zip size MB:", round((out / "upload_pack.zip").stat().st_size / 1e6, 2))

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    raw_root = Path(sys.argv[1]) if len(sys.argv) > 1 else project_root / "data" / "raw"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else project_root / "outputs" / "00_source_profile"
    main(raw_root, out_dir)
