"""Dictionary-free skill candidate mining (Step 5 v2).

Candidates come from spaCy noun chunks and technology-shaped tokens (digits, symbols, acronyms).
A candidate is kept when it appears in enough postings and is over-represented in these postings
compared with general English (log10 lift, using wordfreq). The skill dictionary is not used.
"""

from collections import Counter
import math
import re

import pandas as pd
import spacy
from wordfreq import word_frequency

from common import require_file, write_csv
from config import MIN_CANDIDATE_DOCUMENT_FREQUENCY, STEP_04_DIR, STEP_05_V2_DIR

MODEL_NAME = "en_core_web_sm"
MIN_LOG10_LIFT = 1.5
MIN_LIST_CONTEXT_SHARE = 0.25
MAX_DOC_SHARE = 0.5
MAX_WORDS = 4
MIN_SKILL_CUE_SHARE = 0.1
MIN_CAPITALIZED_SHARE = 0.5
CUE_WINDOW = 100
SKILL_CUE = re.compile(
    r"(?:experience (?:with|in)|proficien\w* (?:with|in)|knowledge of|familiar\w* with|hands-on|"
    r"expertise (?:with|in)|such as|including|tools?|using)\W*(?:\w+\W+){0,3}$",
    re.I,
)
NOISE_PATTERN = re.compile(
    r"^[\d.,+%$-]+$"
    r"|\b(?:over|under|least|additional|within|up to|more than)\s+\d"
    r"|\d+\s*(?:years?|yrs?|hours?|%|months?)\b"
    r"|&|;|\b(?:amp|nbsp|quot)\b"
    r"|\b(?:bachelor|master|diploma|degree|eeo|disabilit\w*|veteran\w*|401k|pto|salary|bonus|"
    r"benefits?|insurance|dental|vision|vacation|holidays?)\b"
    r"|^[a-z]-\d+$",
    re.I,
)
REQUIREMENT_CUE = re.compile(
    r"\b(?:requires?|required|must|requirements?|qualifications?|proficien\w*|experience|"
    r"knowledge|familiar\w*|skills?|preferred|bonus|nice to have|expertise|tools?)\b",
    re.I,
)
LIST_TRIGGER = re.compile(
    r"(?:such as|including|like|with|in|of|using|tools?|experience|proficiency|expertise|familiarity|knowledge)"
    r"\s+(?:[^.;:!?]*)$",
    re.I,
)
LIST_BEFORE = re.compile(r"(?:,|/|\band|\bor)\s*$", re.I)
LIST_AFTER = re.compile(r"^\s*(?:,|/|\band\b|\bor\b)", re.I)
VALID_KEY = re.compile(r"^\.?[a-z0-9][a-z0-9+#./\- ]*$")
SHAPE_TOKEN = re.compile(r"[\d+#./]")
EDGE_WORDS = {
    "a", "an", "the", "your", "our", "their", "its", "this", "that", "these", "those", "strong",
    "excellent", "good", "great", "solid", "proven", "relevant", "related", "various", "similar",
    "including", "such", "as", "and", "or", "of", "with", "in", "to", "for", "on", "at", "from",
    "etc", "e.g", "i.e", "ideal", "plus", "minimum", "least", "key", "core", "new", "modern", "basic",
    "advanced", "deep", "broad", "extensive", "practical", "hands-on", "hands", "knowledge",
    "experience", "experiences", "proficiency", "expertise", "understanding", "familiarity", "ability",
    "working", "years", "year", "bachelor", "bachelors", "master", "masters", "degree", "using", "use",
    "building", "develop", "developing", "per", "all", "any", "some", "more", "other", "others",
    "multiple", "different", "successful", "candidate", "candidates", "you", "we", "they", "us", "who",
}
TRAILING_WORDS = {
    "skills", "skill", "experience", "experiences", "knowledge", "expertise", "tools", "tool",
    "technologies", "technology", "solutions", "solution", "environment", "environments", "principles",
    "concepts", "practices", "processes", "process", "ability", "abilities", "understanding",
    "proficiency", "years", "year", "degree", "role", "roles", "team", "teams", "position", "work",
    "projects", "project", "platform", "platforms", "etc", "preferred", "required", "plus", "background",
}
NOISE_WORDS = {
    "team", "company", "candidate", "candidates", "role", "position", "opportunity", "opportunities",
    "benefit", "benefits", "salary", "compensation", "employer", "employee", "employees", "client",
    "clients", "customer", "customers", "business", "businesses", "people", "person", "time", "problem",
    "problems", "solution", "solutions", "environment", "job", "jobs", "others", "other", "one", "ones",
    "way", "ways", "level", "levels", "help", "support", "group", "groups", "industry", "industries",
    "world", "year", "years", "day", "days", "hours", "location", "locations", "responsibilities",
    "responsibility", "requirements", "requirement", "qualifications", "qualification", "duties", "duty",
    "value", "values", "mission", "market", "demand", "overview", "description", "summary", "email",
    "phone", "etc", "us", "usa", "it", "eeo", "ada", "pto", "401k", "k", "u.s", "degree", "bachelor",
    "master", "high school diploma", "work", "working", "new", "today", "global", "national",
    "department", "organization", "features", "feature", "services", "service", "products", "product",
    "sexual orientation", "gender identity", "national origin", "veteran status", "disability",
    "pregnancy", "equal opportunity", "background check", "paid time off", "health insurance",
    "medical dental", "dental vision", "united states", "states", "state", "amp", "preferred qualifications",
    "basic qualifications", "minimum qualifications", "required qualifications", "job description",
    "about us", "our team", "what you'll do", "computer science", "information systems",
    "information technology", "business administration", "mathematics",
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware",
    "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky",
    "louisiana", "maine", "maryland", "massachusetts", "michigan", "minnesota", "mississippi", "missouri",
    "montana", "nebraska", "nevada", "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island",
    "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming",
    "security", "design", "communication", "communications", "stakeholders", "scalability",
    "collaboration", "leadership", "analysis", "management", "delivery", "outcomes", "reviews",
    "review", "impact", "strategy", "initiatives", "culture", "innovation", "impacts", "results",
    "tasks", "task", "goals", "goal", "requirements", "expectations", "growth", "opportunity",
}
GENERIC_WORDS = {
    "overall", "major", "modern", "another", "one", "multi-step", "multi", "various", "general", "key",
    "latest", "leading", "technology", "technologies", "management", "system", "systems", "business",
    "software", "development", "architecture", "reporting", "workflow", "workflows", "stakeholders",
    "solution", "solutions", "delivery", "outcomes", "scripting", "fundamentals", "methodologies",
    "lifecycle", "process", "processes", "tasks", "approach", "requirements", "data",
}
WORD = re.compile(r"[a-z0-9][a-z0-9+#./-]*")
CANDIDATE_COLUMNS = ["term", "doc_freq", "doc_share", "log10_lift", "has_shape", "capitalized_share",
                     "list_context_share", "requirement_cue_share", "skill_cue_share", "example_context",
                     "candidate_sources", "source_text_field"]


def clean_word(raw: str) -> str:
    return re.sub(r"^[^\w.+#]+|[^\w+#]+$", "", raw)


def normalize_chunk(words: list[str], stop_words: set[str]) -> tuple[str, str] | None:
    """Return (lowercase key, display form) for a phrase, or None when it is not a skill-like phrase."""
    pairs = [(word, word.lower()) for word in (clean_word(raw) for raw in words) if word]
    while pairs and pairs[0][1] in EDGE_WORDS:
        pairs.pop(0)
    while pairs and pairs[-1][1] in TRAILING_WORDS:
        pairs.pop()
    if not pairs or len(pairs) > MAX_WORDS:
        return None
    key = " ".join(lower for _, lower in pairs)
    if key in NOISE_WORDS or len(key) > 40 or not VALID_KEY.match(key) or not re.search(r"[a-z]", key):
        return None
    if NOISE_PATTERN.search(key) or re.search(r"\s(?:and|or)\s", key):
        return None
    if all(word in GENERIC_WORDS for word in key.split()):
        return None
    if all(lower in NOISE_WORDS or lower in stop_words for _, lower in pairs):
        return None
    if len(key) < 2 and key not in {"c", "r"}:
        return None
    return key, " ".join(orig for orig, _ in pairs)


def is_list_context(text: str, start: int, end: int) -> bool:
    """True when a span follows a trigger phrase in its sentence or sits in a comma/and/or list."""
    before = text[max(0, start - 80):start]
    before = re.split(r"[.!?\n]", before)[-1]
    return bool(LIST_TRIGGER.search(before) or LIST_BEFORE.search(before) or LIST_AFTER.search(text[end:end + 4]))


def has_skill_cue(text: str, start: int) -> bool:
    before = re.split(r"[.!?\n]", text[max(0, start - 60):start])[-1]
    return bool(SKILL_CUE.search(before))


def is_plain_english_compound(term: str) -> bool:
    """True for hyphen/slash joins of common English words, such as 'short-term' or 'current/active'."""
    parts = [part for part in re.split(r"[/-]", term.lower()) if part]
    return len(parts) > 1 and not re.search(r"\d", term) and all(
        word_frequency(part, "en") >= 1e-6 for part in parts
    )


def log10_lift(key: str, token_counts: Counter, ngram_counts: Counter, total_tokens: int) -> float:
    """Single words use their own frequency. Phrases use their joint frequency against the geometric
    mean of their words' English frequencies, so 'deep learning' is not judged by 'learning' alone."""
    words = key.split()
    if len(words) == 1:
        in_it = token_counts[key] / max(total_tokens, 1)
        in_english = max(word_frequency(key, "en"), 1e-8)
    else:
        in_it = ngram_counts[key] / max(total_tokens, 1)
        in_english = math.exp(sum(math.log(max(word_frequency(w, "en"), 1e-8)) for w in words) / len(words))
    return math.log10(max(in_it, 1e-12) / in_english)


def collect_candidates(jobs: pd.DataFrame) -> pd.DataFrame:
    nlp = spacy.load(MODEL_NAME, disable=["ner"])
    stop_words = {word.lower() for word in nlp.Defaults.stop_words}
    texts = jobs["description_clean"].fillna("").astype(str).tolist()
    doc_ids = jobs["description_group_id"].astype(str).tolist()

    token_counts = Counter()
    ngram_counts = Counter()
    for text in texts:
        tokens = WORD.findall(text.lower())
        token_counts.update(tokens)
        for n in range(2, MAX_WORDS + 1):
            ngram_counts.update(" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1))
    total_tokens = sum(token_counts.values())

    # Per candidate: display counts, documents, and documents with a requirement cue nearby.
    entries = {}

    def add(key: str, display: str, doc_id: str, text: str, start: int, end: int, source: str,
            capitalized: bool = False) -> None:
        entry = entries.setdefault(key, {"displays": Counter(), "docs": set(), "cue_docs": set(),
                                         "skill_cue_docs": set(), "list_docs": set(), "proper_docs": set(),
                                         "sources": set(), "context": None})
        entry["displays"][display] += 1
        entry["docs"].add(doc_id)
        entry["sources"].add(source)
        if capitalized:
            entry["proper_docs"].add(doc_id)
        window = text[max(0, start - CUE_WINDOW):min(len(text), end + CUE_WINDOW)]
        if REQUIREMENT_CUE.search(window):
            entry["cue_docs"].add(doc_id)
        if has_skill_cue(text, start):
            entry["skill_cue_docs"].add(doc_id)
        if is_list_context(text, start, end):
            entry["list_docs"].add(doc_id)
        if entry["context"] is None:
            entry["context"] = text[max(0, start - 60):min(len(text), end + 60)].replace("\n", " ")

    for doc_id, text, doc in zip(doc_ids, texts, nlp.pipe(texts, batch_size=64)):
        for chunk in doc.noun_chunks:
            if chunk.root.pos_ not in {"NOUN", "PROPN"}:
                continue
            normalized = normalize_chunk(chunk.text.split(), stop_words)
            if normalized:
                capitalized = (len(chunk) == 1 and chunk.root.pos_ == "PROPN"
                               and chunk.text[:1].isupper() and not chunk[0].is_sent_start)
                add(normalized[0], normalized[1], doc_id, text, chunk.start_char, chunk.end_char,
                    "noun_chunk", capitalized)
        for match in re.finditer(r"\S+", text):
            cleaned = clean_word(match.group())
            if not cleaned or not VALID_KEY.match(cleaned.lower()):
                continue
            is_shape = bool(SHAPE_TOKEN.search(cleaned)) and not re.fullmatch(r"[\d.]+", cleaned)
            is_acronym = cleaned.isupper() and 2 <= len(cleaned) <= 6 and cleaned.isalpha()
            if is_shape or is_acronym:
                normalized = normalize_chunk([cleaned], stop_words)
                if normalized:
                    add(normalized[0], normalized[1], doc_id, text, match.start(), match.end(), "token_shape")

    n_docs = len(jobs)
    records = []
    for key, entry in entries.items():
        doc_freq = len(entry["docs"])
        if doc_freq < MIN_CANDIDATE_DOCUMENT_FREQUENCY or doc_freq / n_docs > MAX_DOC_SHARE:
            continue
        display = entry["displays"].most_common(1)[0][0]
        records.append({
            "term": display,
            "doc_freq": doc_freq,
            "doc_share": round(doc_freq / n_docs, 6),
            "log10_lift": round(log10_lift(key, token_counts, ngram_counts, total_tokens), 3),
            "has_shape": bool(SHAPE_TOKEN.search(key)),
            "capitalized_share": round(len(entry["proper_docs"]) / doc_freq, 3),
            "list_context_share": round(len(entry["list_docs"]) / doc_freq, 3),
            "requirement_cue_share": round(len(entry["cue_docs"]) / doc_freq, 3),
            "skill_cue_share": round(len(entry["skill_cue_docs"]) / doc_freq, 3),
            "example_context": entry["context"],
            "candidate_sources": ";".join(sorted(entry["sources"])),
            "source_text_field": "description_clean",
        })
    return pd.DataFrame(records, columns=CANDIDATE_COLUMNS)


def select_candidates(stats: pd.DataFrame, min_lift: float = MIN_LOG10_LIFT,
                      min_list_share: float = MIN_LIST_CONTEXT_SHARE) -> pd.DataFrame:
    single_token = ~stats.term.str.contains(" ")
    compound = stats.term.map(is_plain_english_compound)
    shape_keep = stats.has_shape & single_token & ~compound
    lift_keep = ((stats.log10_lift >= min_lift) & (stats.list_context_share >= min_list_share)
                 & (stats.skill_cue_share >= MIN_SKILL_CUE_SHARE))
    proper_keep = ((stats.capitalized_share >= MIN_CAPITALIZED_SHARE) & single_token
                   & (stats.skill_cue_share >= MIN_SKILL_CUE_SHARE))
    keep = shape_keep | lift_keep | proper_keep
    return stats[keep].sort_values(["doc_freq", "term"], ascending=[False, True]).reset_index(drop=True)


def main() -> None:
    jobs = require_file(STEP_04_DIR / "jobs_desc.csv", ["description_group_id", "description_clean"])
    stats = collect_candidates(jobs)
    result = select_candidates(stats)
    write_csv(result, STEP_05_V2_DIR / "skill_candidates_v2.csv")
    print(f"Unique descriptions scanned: {len(jobs)}; candidates with doc_freq >= {MIN_CANDIDATE_DOCUMENT_FREQUENCY}: {len(result)}.")
    print(result.head(50).to_string(index=False))


if __name__ == "__main__":
    main()
