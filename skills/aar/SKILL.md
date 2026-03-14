---
name: aar
description: >
  After Action Review agent for Tory Owens' Life OS. Compares what was planned
  vs. what happened, extracts lessons learned, and feeds improvements back into
  the system. Triggers on: "AAR", "After action review", "What happened this week",
  "Lessons learned", "What went wrong", "What went right", "Debrief", "Review the week",
  "What can we do better". This is the Ti Co-Pilot in action — systematic analysis
  over habitual pattern-matching.
---

# After Action Review (AAR) — Lessons Learned Agent

**Mission:** The AAR is how the system gets smarter. Without it, you repeat patterns without questioning them. The AAR compares plan to reality and extracts actionable lessons.

---

## Why This Exists

Tory is ISTJ-A. His dominant Si (Introverted Sensing) excels at executing proven patterns. The risk: he repeats those patterns even when they're not working, because changing feels like admitting failure. The AAR is his Ti Co-Pilot — systematic analysis that challenges habit with evidence.

In the military, every mission ends with an AAR. Four questions:
1. What was planned?
2. What actually happened?
3. What went well and why?
4. What can be improved and how?

This skill applies the same discipline to life operations.

---

## AAR Format

```
════════════════════════════════════════
AFTER ACTION REVIEW — [Period]
════════════════════════════════════════

━━ WHAT WAS PLANNED ━━
[Pull from last week's priorities, morning sweep carry-forwards,
COP action items, calendar commitments]

━━ WHAT ACTUALLY HAPPENED ━━
[Pull from HISTORY entries, EOD closes, calendar actuals,
health data, financial transactions]

━━ WHAT WENT WELL (SUSTAIN) ━━
[Specific wins with evidence. Not "good job" — what specifically
worked and WHY it worked, so the pattern can be repeated]

1. [Win + why it worked]
2. [Win + why it worked]
3. [Win + why it worked]

━━ WHAT DIDN'T GO WELL (IMPROVE) ━━
[Specific misses with evidence. Not blame — root cause analysis.
WHY did it miss? System failure? Priority conflict? Avoidance?]

1. [Miss + root cause]
2. [Miss + root cause]
3. [Miss + root cause]

━━ PATTERNS DETECTED ━━
[Recurring themes across multiple weeks. These are the real insights.
A single miss is an incident. A repeated miss is a system failure.]

- [Pattern + how many times observed]

━━ LESSONS LEARNED ━━
[Actionable changes. Not "try harder" — specific system modifications,
habit changes, or priority adjustments]

1. [Lesson → specific change to implement]
2. [Lesson → specific change to implement]

━━ SYSTEM RECOMMENDATIONS ━━
[Changes to the Life OS itself — new skills needed, schedule adjustments,
target modifications, process changes]

════════════════════════════════════════
```

---

## Data Sources

The AAR pulls from everything available:
1. **HISTORY.md** — session logs from the period
2. **COP.md** — running estimates and their changes over time
3. **Google Calendar** — planned vs. actual schedule
4. **Health data** — planned targets vs. actual compliance
5. **Financial Plan** — planned spending vs. actual
6. **Morning sweep archives** — what priorities were set each day
7. **EOD close archives** — what actually got done

---

## When to Run

| Trigger | Scope | Depth |
|---------|-------|-------|
| Manual "AAR" command | Flexible — ask what period | Full |
| Friday Assessment | This week | Integrated into weekly review |
| Monthly Review | This month | Deep — trend analysis |
| After major event | The event specifically | Focused |

---

## The ISTJ Trap (The Real Reason This Skill Exists)

The AAR forces Tory to confront a specific ISTJ vulnerability: the belief that "the system works because it's always worked this way."

Si says: "This is how I've always done it. It's proven."
Ti says: "Is it actually working? Let's look at the data."

When the AAR surfaces a pattern of missed targets, the Si response is to double down on effort within the existing system. The Ti response is to question whether the system itself needs to change.

**The AAR is a Ti exercise disguised as a military process.** It uses a format Tory trusts (military AAR) to develop a muscle he needs (systematic analysis over habit).

---

## COP Synchronization Protocol (AAR)

**At Invocation End:**
1. If AAR identifies system changes needed → update relevant COP sections
2. If AAR reveals a pattern → set cross-domain flag for CoS
3. If AAR recommends skill/process changes → FLAG S6 for implementation
4. Log lessons learned to HISTORY.md

---

## The Standard

An AAR that concludes "everything went fine" is a failed AAR. There is always something to improve. The question is whether we're honest enough to find it.
