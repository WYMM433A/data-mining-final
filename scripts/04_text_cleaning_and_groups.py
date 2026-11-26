"""Clean descriptions conservatively and create listing/description analysis views."""

from collections import Counter, defaultdict
from itertools import combinations
import math
import re

import pandas as pd

from common import require_file, write_csv
from config import NEAR_DUPLICATE_COSINE, OUTPUT_DIR, RANDOM_SEED, RESOURCE_DIR, STEP_03_DIR, STEP_04_DIR

BOILERPLATE = re.compile(
    r"equal opportunity|\bEEO\b|affirmative action|without regard to|reasonable accommodation|"
    r"protected (class|status|veteran)|veteran status|sexual orientation|gender identity|"
    r"national origin|benefits include|we offer|401\(?k\)?|health insurance|dental|"
    r"paid time off|\bPTO\b|about us|our mission|who we are|apply (now|today)|"
    r"click (here|apply)|background check|drug.?free",
    re.I,
)
TOKEN_RE = re.compile(r"(?u)\b\w\w+\b")
SENTENCE_RE = re.compile(r"(?<=[.!?])(?:\s+|(?=\n))")
TITLE_STOPWORDS = {"and", "of", "the", "for"}
REQUIREMENT_RE = re.compile(
    r"\b(?:minimum|basic|required|preferred|desired) qualifications?\b|"
    r"\bqualifications? (?:include|are|required for)\b|"
    r"\b(?:high school diploma|ged|associate(?:'s)?|bachelor(?:'s)?|master(?:'s)?|"
    r"ph\.?d\.?|doctorate|undergraduate degree)\b|"
    r"\b(?:degree|certification|license|licensure)\b.{0,50}\b(?:required|preferred|minimum|must)\b|"
    r"\b(?:at least|minimum of)?\s*\d{1,2}\+?\s+years? (?:of )?experience\b|"
    r"\b(?:experience|expertise|proficiency|proficient|knowledge|skills?)\s+"
    r"(?:with|in|of|using|building|developing|designing|implementing|managing|supporting|working on)\b|"
    r"\b(?:experience|expertise|proficiency|knowledge|background)\s+(?:in\s+)?\w+ing\b|"
    r"\b(?:must have|must possess|ability to|familiarity with)\b",
    re.I,
)


def split_sentences(text: str) -> list[str]:
    lines = str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    sentences = []
    for line in lines:
        sentences.extend(part.strip(" \t-•\u2022") for part in SENTENCE_RE.split(line) if part.strip(" \t-•\u2022"))
    return sentences


def normalized_sentence(sentence: str) -> str:
    return re.sub(r"\s+", " ", sentence.lower()).strip()


def build_template_sentences(base: pd.DataFrame) -> dict[str, set[str]]:
    per_company: dict[str, set[str]] = {}
    per_sentence_docs: dict[str, Counter] = defaultdict(Counter)
    for row in base.to_dict("records"):
        company = str(row["companyName"]).strip().lower()
        per_company.setdefault(company, set()).add(row["desc_hash"])
        seen = {normalized_sentence(item) for item in split_sentences(row["description_raw"])}
        for sentence in seen:
            per_sentence_docs[company][sentence] += 1
    templates = {}
    for company, groups in per_company.items():
        if len(groups) >= 5:
            templates[company] = {sentence for sentence, count in per_sentence_docs[company].items() if count >= 3}
        else:
            templates[company] = set()
    return templates


def build_protected_skill_pattern(dictionary: pd.DataFrame) -> re.Pattern:
    terms = set()
    short_allowlist = {"ai", "ui", "ml", "bi", "qa", "js", "ts"}
    for row in dictionary.to_dict("records"):
        if str(row.get("is_soft", "0")).strip().lower() in {"1", "true", "yes"}:
            continue
        for term in [row.get("canonical", ""), *str(row.get("aliases", "")).split("|")]:
            term = str(term).strip()
            if not term:
                continue
            compact = re.sub(r"[^a-z0-9]", "", term.lower())
            if len(compact) < 3 and compact not in short_allowlist and not re.search(r"[^a-zA-Z0-9\s]", term):
                continue
            terms.add(term)
    alternatives = []
    for term in sorted(terms, key=len, reverse=True):
        alternatives.append(r"\s+".join(re.escape(part) for part in term.split()))
    if not alternatives:
        return re.compile(r"(?!)")
    return re.compile(
        r"(?<![A-Za-z0-9+#.])(?:" + "|".join(alternatives) + r")(?![A-Za-z0-9+#.])",
        re.I,
    )


def build_current_skill_dictionary() -> pd.DataFrame:
    """Canonical/aliases table built from the curated 230-skill mining dictionary (skill_shortlist_final.csv
    + Normalization & Alias Mapping), replacing the older resources/skill_dictionary.csv reference."""
    shortlist = pd.read_csv(OUTPUT_DIR / "09_job_skill_matrix" / "skill_shortlist_final.csv")
    mapping = pd.read_csv(OUTPUT_DIR.parent / "skill_extraction" / "Normalization & Alias Mapping.csv",
                           encoding="utf-8-sig")
    usable_actions = {"Retained", "Normalized / reclassified", "Alias merged", "Confirmed"}
    grouped = (mapping[mapping.action.isin(usable_actions)]
               .groupby("canonical_skill")["original_term"].apply(list).to_dict())
    rows = []
    for canonical in shortlist.loc[shortlist.mining_status == "include", "canonical_skill"]:
        aliases = list(dict.fromkeys(grouped.get(canonical, []) + [canonical]))
        rows.append({"canonical": canonical, "aliases": "|".join(aliases), "is_soft": "0"})
    return pd.DataFrame(rows)


def clean_one(
    text: str,
    company: str,
    templates: dict[str, set[str]],
    protected_skills: re.Pattern,
    examples: list[dict],
    protected_examples: list[dict],
    job_id: str,
) -> tuple[str, str]:
    keep_clean, keep_similarity = [], []
    template_sentences = templates.get(str(company).strip().lower(), set())
    for sentence in split_sentences(text):
        normalized = normalized_sentence(sentence)
        if BOILERPLATE.search(sentence):
            examples.append({
                "job_id": job_id, "rule": "boilerplate_regex",
                "scope": "description_clean;description_similarity", "sentence": sentence,
            })
            continue
        if normalized in template_sentences:
            protection = []
            if REQUIREMENT_RE.search(sentence):
                protection.append("requirement_phrase")
            if education_level(sentence) != "not mentioned":
                protection.append("education_signal")
            if minimum_experience(sentence):
                protection.append("experience_years_signal")
            if protected_skills.search(sentence):
                protection.append("skill_dictionary_term")
            if protection:
                keep_clean.append(sentence)
                protected_examples.append({
                    "job_id": job_id, "rule": "company_template",
                    "protection_reason": ";".join(protection),
                    "scope": "description_similarity_only", "sentence": sentence,
                })
            else:
                examples.append({
                    "job_id": job_id, "rule": "company_template",
                    "scope": "description_clean;description_similarity", "sentence": sentence,
                })
            # Similarity text strips all repeated company templates, including protected requirements.
            continue
        keep_clean.append(sentence)
        keep_similarity.append(sentence)
    return "\n".join(keep_clean).strip(), "\n".join(keep_similarity).strip()


def titleless_text(text: str, title_norm: str) -> str:
    words = {token for token in re.findall(r"[a-z0-9+#.]+", str(title_norm).lower()) if token not in TITLE_STOPWORDS}
    if not words:
        return text
    pattern = re.compile(r"(?<![A-Za-z0-9+#])(?:" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")(?![A-Za-z0-9+#])", re.I)
    return re.sub(r"\s+", " ", pattern.sub(" ", text)).strip()


def education_level(text: str) -> str:
    patterns = [
        (0, r"\b(high school|high-school|GED)\b", "high_school"),
        (1, r"\bassociate(?:'s)?\b", "associate"),
        (2, r"\bbachelor(?:'s)?\b|\bB\.S\.\b|\bB\.A\.\b|\bundergraduate degree\b", "bachelor"),
        (3, r"\bmaster(?:'s)?\b|\bM\.S\.\b|\bM\.A\.\b|\bMBA\b", "master"),
        (4, r"\bPh\.?D\.?\b|\bdoctorate\b|\bdoctoral degree\b", "phd"),
    ]
    found = [(level, label) for level, pattern, label in patterns if re.search(pattern, text, re.I)]
    return min(found)[1] if found else "not mentioned"


def minimum_experience(text: str) -> str:
    values = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        if re.search(r"\bexperience\b", sentence, re.I):
            for match in re.finditer(r"\b(\d{1,2})\s*(?:\+\s*)?years?\b", sentence, re.I):
                number = int(match.group(1))
                if 1 <= number <= 15:
                    values.append(number)
    return str(min(values)) if values else ""


def tfidf_edges(base: pd.DataFrame, threshold: float) -> list[tuple[str, str, float]]:
    """Pure-Python sparse TF-IDF cosine edges, compared only within each company."""
    edges = []
    for _, company_rows in base.groupby("companyName", sort=False):
        docs = company_rows[["desc_hash", "description_similarity"]].to_dict("records")
        if len(docs) < 2:
            continue
        tokens_by_doc = [Counter(TOKEN_RE.findall(str(doc["description_similarity"]).lower())) for doc in docs]
        doc_freq = Counter()
        for counts in tokens_by_doc:
            doc_freq.update(counts.keys())
        n_docs = len(docs)
        vectors = []
        inverted: dict[str, list[tuple[int, float]]] = defaultdict(list)
        for index, counts in enumerate(tokens_by_doc):
            weighted = {}
            for token, count in counts.items():
                idf = math.log((1 + n_docs) / (1 + doc_freq[token])) + 1.0
                weighted[token] = count * idf
            norm = math.sqrt(sum(weight * weight for weight in weighted.values()))
            vector = {token: weight / norm for token, weight in weighted.items()} if norm else {}
            vectors.append(vector)
            for token, weight in vector.items():
                inverted[token].append((index, weight))

        pair_dots: dict[tuple[int, int], float] = defaultdict(float)
        for postings in inverted.values():
            if len(postings) > 1:
                for (i, wi), (j, wj) in combinations(postings, 2):
                    pair_dots[(i, j)] += wi * wj
        for (i, j), score in pair_dots.items():
            if score >= threshold:
                edges.append((docs[i]["desc_hash"], docs[j]["desc_hash"], float(score)))
    return edges


def connected_components(keys: list[str], edges: list[tuple[str, str, float]]) -> dict[str, str]:
    parent = {key: key for key in keys}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    for left, right, _ in edges:
        a, b = find(left), find(right)
        if a != b:
            low, high = sorted((a, b))
            parent[high] = low
    return {key: find(key) for key in keys}


def main() -> None:
    source = require_file(STEP_03_DIR / "jobs_family.csv", [
        "id", "companyName", "descriptionText", "title", "title_norm", "job_family", "desc_hash", "postedAt",
    ])
    source = source.copy().rename(columns={
        "descriptionText": "description_raw",
        "description_group_id": "initial_description_group_id",
        "description_group_size": "initial_description_group_size",
    })
    source["n_words"] = source["description_raw"].str.split().str.len()
    dictionary = build_current_skill_dictionary()
    protected_skills = build_protected_skill_pattern(dictionary)

    # One representative text per exact company+description hash is enough to learn templates.
    base = source.drop_duplicates("desc_hash")[["id", "desc_hash", "companyName", "description_raw"]].copy()
    templates = build_template_sentences(base)
    removed_examples: list[dict] = []
    protected_examples: list[dict] = []
    cleaned_by_hash = {}
    similarity_by_hash = {}
    for row in base.to_dict("records"):
        cleaned, similarity = clean_one(
            row["description_raw"], row["companyName"], templates, protected_skills,
            removed_examples, protected_examples, row["id"],
        )
        cleaned_by_hash[row["desc_hash"]] = cleaned
        similarity_by_hash[row["desc_hash"]] = similarity
    source["description_clean"] = source["desc_hash"].map(cleaned_by_hash).fillna("")
    source["description_similarity"] = source["desc_hash"].map(similarity_by_hash).fillna("")
    source["description_sim"] = [titleless_text(text, title) for text, title in zip(source.description_similarity, source.title_norm)]
    # Derive structured requirements from untouched source text so cleaning cannot erase them.
    source["education_min"] = source.description_raw.map(education_level)
    source["min_years_experience"] = source.description_raw.map(minimum_experience)

    base["description_clean"] = base["desc_hash"].map(cleaned_by_hash).fillna("")
    base["description_similarity"] = base["desc_hash"].map(similarity_by_hash).fillna("")
    # Candidate near-duplicate edges are surfaced for review. The primary table
    # keeps exact company+description groups until the team approves merges.
    edges = tfidf_edges(base, NEAR_DUPLICATE_COSINE)
    id_by_hash = {key: index + 1 for index, key in enumerate(sorted(base.desc_hash.tolist()))}
    source["description_group_id"] = source.desc_hash.map(id_by_hash).astype(int)

    grouped = source.groupby("description_group_id").agg(
        description_group_size=("id", "size"),
        n_distinct_titles_in_group=("title", "nunique"),
        n_distinct_families_in_group=("job_family", "nunique"),
    )
    source = source.join(grouped, on="description_group_id")
    source["family_group_ambiguous"] = source.n_distinct_families_in_group.gt(1)

    source["_posted_sort"] = pd.to_datetime(source.postedAt, errors="coerce")
    reps = source.sort_values(
        ["description_group_id", "_posted_sort", "n_words", "id"],
        ascending=[True, False, False, True], kind="mergesort",
    ).drop_duplicates("description_group_id")
    listing = source.drop(columns=["_posted_sort"])
    desc = reps.drop(columns=["_posted_sort"])
    write_csv(listing, STEP_04_DIR / "jobs_listing.csv")
    write_csv(desc, STEP_04_DIR / "jobs_desc.csv")

    if removed_examples:
        sample = pd.DataFrame(removed_examples).sample(n=min(50, len(removed_examples)), random_state=RANDOM_SEED)
    else:
        sample = pd.DataFrame(columns=["job_id", "rule", "scope", "sentence"])
    write_csv(pd.DataFrame(removed_examples, columns=["job_id", "rule", "scope", "sentence"]), STEP_04_DIR / "boilerplate_removed_all.csv")
    write_csv(sample, STEP_04_DIR / "boilerplate_removed_examples.csv")
    write_csv(pd.DataFrame(protected_examples, columns=["job_id", "rule", "protection_reason", "scope", "sentence"]), STEP_04_DIR / "company_template_protected.csv")
    edge_context = base.set_index("desc_hash")[["companyName", "id"]].to_dict("index")
    edge_rows = []
    for left, right, score in edges:
        edge_rows.append({
            "company": edge_context[left]["companyName"],
            "desc_hash_a": left, "job_id_a": edge_context[left]["id"],
            "desc_hash_b": right, "job_id_b": edge_context[right]["id"],
            "cosine": score,
        })
    write_csv(pd.DataFrame(edge_rows, columns=["company", "desc_hash_a", "job_id_a", "desc_hash_b", "job_id_b", "cosine"]), STEP_04_DIR / "near_duplicate_edges.csv")
    empty_or_short = listing.description_clean.str.split().str.len().lt(30)
    write_csv(listing.loc[empty_or_short, ["id", "title", "companyName", "description_group_id", "description_clean"]], STEP_04_DIR / "cleaned_description_review.csv")

    print(f"Listings: {len(listing)}; exact company-description groups: {base.shape[0]}; near-duplicate edges: {len(edges)}.")
    print(f"Exact description groups retained: {len(desc)}; groups with multiple titles={int(desc.n_distinct_titles_in_group.gt(1).sum())}; multiple families={int(desc.family_group_ambiguous.sum())}.")
    print(f"Near-duplicate edges at cosine >= {NEAR_DUPLICATE_COSINE:.2f} are review candidates only; they were not merged.")
    print(f"Empty/under-30-word cleaned descriptions flagged: {int(empty_or_short.sum())}; no records were removed.")


if __name__ == "__main__":
    main()
