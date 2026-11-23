"""Split a pasted itinerary into its days before the parser reads it (decision 2026-11-23).

One call for a whole trip asked the model for 50+ items in one answer: it sometimes closed the
answer after day 1 (a "※" remark read as the end: the 4-day Prague paste read 10 of 51 time
lines), and an answer that long takes over a minute on the default model. One call per day is
short, runs in parallel, and a day that stops early is asked again on its own.

Rule-based and conservative: a line is a day heading only when it starts like one ("DAY 2",
"Day 2", "2일차", "2日目", "第2天", "1월 25일"). Fewer than two headings: the text stays whole,
as before. Text above the first heading goes with the first day.
"""

import re
from itertools import pairwise

_HEADING_RE = re.compile(
    r"""^\s*[\[(<#*\-•]*\s*(?:
        day\s*[-.]?\s*\d{1,2}(?!\s*[:시])     # DAY 2, Day-2, day.2 (not "Day 2:30")
      | \d{1,2}\s*일\s*차                    # 2일차
      | \d{1,2}\s*日目                       # 2日目
      | 第\s*\d{1,2}\s*[天日]                # 第2天
      | \d{1,2}\s*월\s*\d{1,2}\s*일           # 1월 25일
    )""",
    re.IGNORECASE | re.VERBOSE,
)


def is_day_heading(line: str) -> bool:
    return bool(_HEADING_RE.match(line))


def split_days(text: str) -> list[str]:
    """The text cut at its day headings, in order; [text] when it has fewer than two."""
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if is_day_heading(line)]
    if len(starts) < 2:
        return [text]
    cuts = [0, *starts[1:], len(lines)]  # the preamble stays with the first day
    chunks = ["\n".join(lines[a:b]).strip() for a, b in pairwise(cuts)]
    return [c for c in chunks if c]
