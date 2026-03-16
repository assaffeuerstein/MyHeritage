# MyHeritage Duplicate Finder

A Python script that detects duplicate person entries in a MyHeritage family tree CSV export.

## Input

`MyHeritage.csv` — a CSV export from MyHeritage containing one row per person with the following columns:

| Column | Description |
|---|---|
| `#` | Row number |
| `Identifier` | MyHeritage internal ID |
| `Gender` | `M` or `F` |
| `Name` | Full name (may include maiden name in `(born ...)` format) |
| `Relationship` | Relationship to the tree owner (e.g. "Your grandfather") |
| `Birth date` | Free-text birth date |
| `Birth place` | Free-text birth place |
| `Death date` | Free-text death date |
| `Death place` | Free-text death place |

## Algorithm

The script runs two phases. Phase 1 catches exact-name duplicates; Phase 2 catches duplicates where the same person was entered under slightly different names.

### Phase 1 — Exact name match

All records are grouped into buckets where every record in a bucket shares the **exact same `Name`** value. Any bucket with fewer than two records is skipped.

For every pair of records that share the same name, the script checks the `Relationship`, `Birth date`, and `Death date` fields and applies one of two rules:

#### Rule A — Same relationship

If both records have the **same `Relationship`** value, they are flagged as duplicates **unless** their dates actively contradict each other. A contradiction means both records have a non-empty value for a date field and those values differ.

| Birth dates | Death dates | Verdict |
|---|---|---|
| both empty, or only one filled, or both match | both empty, or only one filled, or both match | **Duplicate** |
| both filled and different | *(any)* | Not a duplicate |
| *(any)* | both filled and different | Not a duplicate |

> Rationale: Two people with the same name appearing in the same relational position in the tree are very likely the same person, unless their known dates prove otherwise.

#### Rule B — Different relationship

If the two records have **different `Relationship`** values, a stronger signal is required. They are flagged as duplicates **only if** at least one date field (birth or death) is present on both records **and matches exactly**.

| Birth dates match? | Death dates match? | Verdict |
|---|---|---|
| Yes | *(any)* | **Duplicate** |
| *(any)* | Yes | **Duplicate** |
| No positive match on either | — | Not a duplicate |

> Rationale: Different relationship labels may indicate the same person was entered twice from different branches of the tree. A matching date provides the corroborating evidence needed to flag them.

### Phase 2 — Similar name match (date-triggered)

This phase reverses the lookup direction: instead of "same name, check dates" it does **"same date, check names"**. It catches duplicates where the same person was entered with a slightly different spelling, with or without a middle name, or under a married vs. maiden name.

#### Step 1 — Group by date

Records are grouped by **normalized birth date** and by **normalized death date** (trailing `?` is stripped so that `1942?` matches `1942`). Each date bucket with two or more records is examined.

#### Step 2 — Filter out obvious non-matches

For each pair of records sharing a date, the script skips the pair if any of the following are true:

- The names are identical (already handled in Phase 1).
- The genders are both known and different.
- The **other** date field conflicts (e.g. pair was grouped by birth date but their death dates are both present and different).

#### Step 3 — Name similarity check

Each name is parsed into components: **first name**, **middle name(s)**, **last name**, and **maiden name** (extracted from the `(born ...)` suffix).

A pair passes the name check only when **all three** conditions are met:

1. **First names must be similar** — compared using exact match, prefix match (minimum 3 characters), or string similarity ratio >= 0.70. Middle-name-only overlap is deliberately ignored because siblings in the same family tree often share a patronymic or family middle name.
2. **Family names must link** — at least one last-name or maiden-name variant from each record must be similar to one from the other (same comparison logic as above).
3. **Maiden names must not conflict** — if both records carry a maiden name and they are not similar, the pair is rejected.

#### Step 4 — Report

Each match is printed once as a "Possible duplicate" with an explanation of the name similarity evidence and the date that triggered the comparison.

## Usage

```bash
python3 duplicate_finder.py
```

The script expects `MyHeritage.csv` in the current working directory.

## Requirements

Python 3 (standard library only — uses `csv`, `re`, `collections.defaultdict`, and `difflib.SequenceMatcher`).
