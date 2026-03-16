#!/usr/bin/env python3

import csv
import re
from collections import defaultdict
from difflib import SequenceMatcher

NAME_SIMILARITY_THRESHOLD = 0.70


# ── Helper utilities ─────────────────────────────────────────

def parse_name(full_name):
    """Parse 'First [Middle…] Last (born Maiden)' into components."""
    maiden = None
    born_match = re.search(r'\(born\s+(.+?)\)', full_name)
    if born_match:
        maiden = born_match.group(1).strip()
        full_name = full_name[:born_match.start()] + full_name[born_match.end():]
        full_name = full_name.strip()
    parts = full_name.split()
    if not parts:
        return {'first': '', 'middle': [], 'last': '', 'maiden': maiden}
    if len(parts) == 1:
        return {'first': parts[0], 'middle': [], 'last': '', 'maiden': maiden}
    return {
        'first': parts[0],
        'middle': parts[1:-1],
        'last': parts[-1],
        'maiden': maiden,
    }


def _is_fuzzy_match(a, b):
    """True when two non-empty strings look like the same name part."""
    lo_a, lo_b = a.lower(), b.lower()
    if lo_a == lo_b:
        return True
    if min(len(lo_a), len(lo_b)) >= 3 and (lo_a.startswith(lo_b) or lo_b.startswith(lo_a)):
        return True
    return SequenceMatcher(None, lo_a, lo_b).ratio() >= NAME_SIMILARITY_THRESHOLD


def names_are_similar(name_a, name_b):
    """Check whether two *different* name strings plausibly refer to the same
    person.  Requires BOTH a first-name match AND a family-name link.
    Middle-name-only overlap is not enough (siblings often share those).
    Returns (is_similar, explanation).
    """
    if name_a == name_b:
        return False, ''

    pa, pb = parse_name(name_a), parse_name(name_b)

    # --- first-name gate (must pass) ---
    first_a, first_b = pa['first'], pb['first']
    if not first_a or not first_b or not _is_fuzzy_match(first_a, first_b):
        return False, ''

    if first_a.lower() == first_b.lower():
        given_desc = f"same first name '{first_a}'"
    else:
        given_desc = f"similar first names '{first_a}'/'{first_b}'"

    # --- family-name link ---
    families_a = [f for f in (pa['last'], pa['maiden']) if f]
    families_b = [f for f in (pb['last'], pb['maiden']) if f]

    family_link = None
    for fa in families_a:
        for fb in families_b:
            if _is_fuzzy_match(fa, fb):
                family_link = (
                    f"shared family name '{fa}'"
                    if fa.lower() == fb.lower()
                    else f"similar family names '{fa}'/'{fb}'"
                )
                break
        if family_link:
            break

    if not family_link:
        return False, ''

    # --- maiden-name conflict → definitely different people ---
    if (pa['maiden'] and pb['maiden']
            and not _is_fuzzy_match(pa['maiden'], pb['maiden'])):
        return False, ''

    return True, f'{family_link}, {given_desc}'


def normalize_date(d):
    """Strip trailing '?' and whitespace so '1942?' matches '1942'."""
    return d.strip().rstrip('?').strip()


def fmt(record):
    """One-line human-readable summary of a record."""
    parts = [f"[#{record['#']}] {record['Name']}"]
    if record['Relationship']:
        parts.append(record['Relationship'])
    bd = record['Birth date'].strip()
    dd = record['Death date'].strip()
    if bd:
        parts.append(f'Born: {bd}')
    if dd:
        parts.append(f'Died: {dd}')
    return ' | '.join(parts)


# ── Read CSV ─────────────────────────────────────────────────

with open('MyHeritage.csv', newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    data = list(reader)

reported = set()

# ── Phase 1: Exact name match ───────────────────────────────

print('=' * 70)
print('PHASE 1 — Exact name matches')
print('=' * 70)
print()

by_name = defaultdict(list)
for i, record in enumerate(data):
    by_name[record['Name']].append((i, record))

phase1_count = 0

for name, records in by_name.items():
    if len(records) < 2:
        continue
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            idx_a, rec_a = records[i]
            idx_b, rec_b = records[j]
            pair = (idx_a, idx_b)
            if pair in reported:
                continue

            rel_a = rec_a['Relationship']
            rel_b = rec_b['Relationship']
            birth_a = rec_a['Birth date'].strip()
            birth_b = rec_b['Birth date'].strip()
            death_a = rec_a['Death date'].strip()
            death_b = rec_b['Death date'].strip()

            is_duplicate = False
            reason = ''

            if rel_a == rel_b:
                birth_conflict = bool(birth_a and birth_b and birth_a != birth_b)
                death_conflict = bool(death_a and death_b and death_a != death_b)
                if not birth_conflict and not death_conflict:
                    is_duplicate = True
                    reason = f'same name and relationship ({rel_a!r})'
            else:
                birth_match = bool(birth_a and birth_b and birth_a == birth_b)
                death_match = bool(death_a and death_b and death_a == death_b)
                if birth_match or death_match:
                    is_duplicate = True
                    matched = []
                    if birth_match:
                        matched.append(f'birth date {birth_a!r}')
                    if death_match:
                        matched.append(f'death date {death_a!r}')
                    reason = (
                        f'same name, different relationships '
                        f'({rel_a!r} vs {rel_b!r}), '
                        f'but matching {" and ".join(matched)}'
                    )

            if is_duplicate:
                reported.add(pair)
                phase1_count += 1
                print(f'Duplicate found ({reason}):')
                print(f'  Record 1: {fmt(rec_a)}')
                print(f'  Record 2: {fmt(rec_b)}')
                print()

if phase1_count == 0:
    print('  No exact-name duplicates found.')
    print()

# ── Phase 2: Fuzzy name match (triggered by shared date) ────

print('=' * 70)
print('PHASE 2 — Similar name matches (triggered by shared date)')
print('=' * 70)
print()

by_birth = defaultdict(list)
by_death = defaultdict(list)

for i, record in enumerate(data):
    bd = normalize_date(record['Birth date'])
    dd = normalize_date(record['Death date'])
    if bd:
        by_birth[bd].append((i, record))
    if dd:
        by_death[dd].append((i, record))

phase2_count = 0


def check_fuzzy_pairs(date_groups, date_label):
    """Compare records sharing a date but carrying different names."""
    count = 0
    for date_val, records in date_groups.items():
        if len(records) < 2:
            continue
        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                idx_a, rec_a = records[i]
                idx_b, rec_b = records[j]
                pair = (idx_a, idx_b)
                if pair in reported:
                    continue
                if rec_a['Name'] == rec_b['Name']:
                    continue

                g_a = rec_a.get('Gender', '').strip()
                g_b = rec_b.get('Gender', '').strip()
                if g_a and g_b and g_a != g_b:
                    continue

                ba = normalize_date(rec_a['Birth date'])
                bb = normalize_date(rec_b['Birth date'])
                da = normalize_date(rec_a['Death date'])
                db = normalize_date(rec_b['Death date'])
                if ba and bb and ba != bb:
                    continue
                if da and db and da != db:
                    continue

                similar, explanation = names_are_similar(
                    rec_a['Name'], rec_b['Name']
                )
                if similar:
                    reported.add(pair)
                    count += 1
                    print(
                        f'Possible duplicate ({explanation}; '
                        f'matching {date_label} {date_val!r}):'
                    )
                    print(f'  Record 1: {fmt(rec_a)}')
                    print(f'  Record 2: {fmt(rec_b)}')
                    print()
    return count


phase2_count += check_fuzzy_pairs(by_birth, 'birth date')
phase2_count += check_fuzzy_pairs(by_death, 'death date')

if phase2_count == 0:
    print('  No similar-name duplicates found.')
    print()

# ── Summary ──────────────────────────────────────────────────

print('=' * 70)
print(
    f'Total: {phase1_count} exact-name + {phase2_count} similar-name '
    f'= {phase1_count + phase2_count} potential duplicates'
)
print('=' * 70)
