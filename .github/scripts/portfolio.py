#!/usr/bin/env python3
"""Add entries to and organize the project table in profile/README.md.

Usage:
  portfolio.py add  --project NAME --project-url URL --hackathon NAME
                    [--hackathon-url URL] --date "Oct 24-25, 2026"  (day required)
                    --members "user1, user2, name=https://link"
  portfolio.py edit --current "Dependency Domino" [--project NAME]
                    [--project-url URL] [--hackathon NAME]
                    [--hackathon-url URL|-] [--date DATE] [--members LIST]
                    (blank fields are kept; --members replaces the whole list)
  portfolio.py sort

Sort rules:
  * Rows are ordered by date, newest first.
  * Rows sharing the same date are grouped by hackathon (A-Z), and within a
    hackathon, by project name (A-Z).
  * Team members inside each row are sorted A-Z (case-insensitive).
"""
import argparse
import re
import sys
from pathlib import Path

README = Path(__file__).resolve().parents[2] / "profile" / "README.md"
MEMBER_SEP = " &nbsp;•&nbsp; "
LINK_RE = re.compile(r"^\[(?P<text>.*?)\]\((?P<url>.*?)\)$")
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
# "Oct 24-25, 2026", "Mar 21, 2026", "Jun 2025", "Oct 31-Nov 1, 2026"
DATE_RE = re.compile(
    r"^(?P<mon>[A-Za-z]{3})[a-z]*\.?"
    r"(?:\s+(?P<day>\d{1,2}))?"
    r"(?:\s*-\s*(?:[A-Za-z]{3}[a-z]*\.?\s+)?\d{1,2})?"
    r",?\s+(?P<year>\d{4})$"
)


def link_text(cell: str) -> str:
    m = LINK_RE.match(cell.strip())
    return (m.group("text") if m else cell).strip()


def date_key(date: str, require_day: bool = False):
    m = DATE_RE.match(date.strip())
    if (not m or m.group("mon").lower() not in MONTHS
            or (require_day and not m.group("day"))):
        raise ValueError(
            f"Unrecognized date '{date}'. Use a day or day range, e.g. "
            "'Mar 21, 2026', 'Oct 24-25, 2026' or 'Oct 31-Nov 1, 2026'.")
    return (int(m.group("year")), MONTHS[m.group("mon").lower()],
            int(m.group("day") or 0))


def split_row(line: str):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def join_row(cells):
    return "| " + " | ".join(cells) + " |"


def sort_members(cell: str) -> str:
    members = [m.strip() for m in cell.split("&nbsp;•&nbsp;") if m.strip()]
    members.sort(key=lambda m: link_text(m).lower())
    return MEMBER_SEP.join(members)


def load():
    lines = README.read_text(encoding="utf-8").splitlines()
    # Table = header line followed by the |:-:| separator line.
    for i in range(len(lines) - 1):
        if lines[i].lstrip().startswith("|") and re.match(
                r"^\s*\|[\s:\-|]+\|\s*$", lines[i + 1]):
            start = i + 2
            end = start
            while end < len(lines) and lines[end].lstrip().startswith("|"):
                end += 1
            return lines, start, end
    sys.exit(f"No markdown table found in {README}")


def organize(rows):
    parsed = [split_row(r) for r in rows if r.strip()]
    for cells in parsed:
        if len(cells) != 4:
            sys.exit(f"Row does not have 4 columns: {join_row(cells)}")
        cells[3] = sort_members(cells[3])
    # Sort ascending by the secondary keys, then stable-sort by date desc.
    parsed.sort(key=lambda c: (link_text(c[1]).lower(), link_text(c[0]).lower()))
    parsed.sort(key=lambda c: date_key(c[2]), reverse=True)
    return [join_row(c) for c in parsed]


def save(lines, start, end, rows):
    out = lines[:start] + rows + lines[end:]
    README.write_text("\n".join(out) + "\n", encoding="utf-8")


def clean(value: str) -> str:
    return value.replace("|", "\\|").strip()


def cmd_sort(_args):
    lines, start, end = load()
    save(lines, start, end, organize(lines[start:end]))
    print("Table organized.")


def link_url(cell: str) -> str:
    m = LINK_RE.match(cell.strip())
    return m.group("url").strip() if m else ""


def make_cell(text: str, url: str) -> str:
    return f"[{text}]({url})" if url else text


def parse_members(value: str) -> str:
    members = []
    for raw in value.split(","):
        raw = raw.strip().lstrip("@")
        if not raw:
            continue
        custom = re.match(r"^([^=/:]+)=(\S+)$", raw)
        if custom:  # custom link, e.g. name=https://devpost.com/name
            name, url = custom.group(1).strip(), custom.group(2).strip()
        elif re.match(r"^https?://", raw):  # e.g. https://github.com/user
            url = raw.rstrip("/")
            name = url.rsplit("/", 1)[-1]
        else:  # bare GitHub username
            name, url = raw, f"https://github.com/{raw}"
        members.append(f"[{clean(name)}]({url})")
    if not members:
        sys.exit("At least one team member is required.")
    return MEMBER_SEP.join(members)


def cmd_add(args):
    date_key(args.date, require_day=True)  # validate early
    project = f"[{clean(args.project)}]({args.project_url.strip()})"
    hackathon = make_cell(clean(args.hackathon), args.hackathon_url.strip())
    members = parse_members(args.members)

    lines, start, end = load()
    existing = {link_text(split_row(r)[0]).lower() for r in lines[start:end]}
    if link_text(project).lower() in existing:
        sys.exit(f"Project '{args.project}' is already in the table.")

    row = join_row([project, hackathon, args.date.strip(), members])
    save(lines, start, end, organize(lines[start:end] + [row]))
    print(f"Added {args.project}.")


CLEAR = {"-", "none"}  # typed into an optional link field to remove the link


def cmd_edit(args):
    fields = [args.project, args.project_url, args.hackathon,
              args.hackathon_url, args.date, args.members]
    if not any(f.strip() for f in fields):
        sys.exit("Nothing to change: fill in at least one field.")
    lines, start, end = load()
    rows = [split_row(r) for r in lines[start:end] if r.strip()]
    target = args.current.strip().lower()
    matches = [c for c in rows if link_text(c[0]).lower() == target]
    if not matches:
        names = ", ".join(sorted((link_text(c[0]) for c in rows), key=str.lower))
        sys.exit(f"No project named '{args.current}'. Projects: {names}")
    cells = matches[0]
    v = lambda s: (s or "").strip()

    # Project name / URL
    name, url = link_text(cells[0]), link_url(cells[0])
    if v(args.project):
        new = v(args.project).lower()
        if new != target and any(link_text(c[0]).lower() == new for c in rows):
            sys.exit(f"Project '{args.project}' is already in the table.")
        name = clean(args.project)
    if v(args.project_url):
        url = v(args.project_url)
    cells[0] = make_cell(name, url)

    # Hackathon name / URL ("-" or "none" removes the link)
    hname, hurl = link_text(cells[1]), link_url(cells[1])
    if v(args.hackathon):
        hname = clean(args.hackathon)
    if v(args.hackathon_url):
        hurl = "" if v(args.hackathon_url).lower() in CLEAR else v(args.hackathon_url)
    cells[1] = make_cell(hname, hurl)

    if v(args.date):
        date_key(args.date, require_day=True)
        cells[2] = v(args.date)
    if v(args.members):
        cells[3] = parse_members(args.members)

    save(lines, start, end, organize([join_row(c) for c in rows]))
    print(f"Edited {args.current}.")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--project", required=True)
    a.add_argument("--project-url", required=True)
    a.add_argument("--hackathon", required=True)
    a.add_argument("--hackathon-url", default="")
    a.add_argument("--date", required=True)
    a.add_argument("--members", required=True)
    a.set_defaults(func=cmd_add)
    e = sub.add_parser("edit")
    e.add_argument("--current", required=True, help="current project display name")
    for flag in ["--project", "--project-url", "--hackathon",
                 "--hackathon-url", "--date", "--members"]:
        e.add_argument(flag, default="")
    e.set_defaults(func=cmd_edit)
    sub.add_parser("sort").set_defaults(func=cmd_sort)
    args = p.parse_args()
    try:
        args.func(args)
    except ValueError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
