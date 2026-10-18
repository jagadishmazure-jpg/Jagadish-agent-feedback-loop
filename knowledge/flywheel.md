# The Product → Data → Model flywheel

Distilled notes on the iteration loop at the heart of AI engineering:
deployed products generate usage data, that data becomes evals and
training signal, and the improved model/config ships back into the
product. Deployments that skip the loop decay — the world moves on,
the model doesn't.

## Why deployments decay

1. **No signal capture.** Users correct the agent every day; if nobody
   records it, the same mistake repeats forever.
2. **Evals frozen at launch.** The golden set reflects launch-day
   understanding. Production keeps teaching new lessons the evals never
   learn, so regressions ship silently.
3. **Implicit signals ignored.** Most dissatisfaction is never typed as
   feedback — it shows up as rephrased questions, undone tool calls,
   and abandoned sessions.

## Explicit vs implicit signals

| | Explicit | Implicit |
|---|---|---|
| Examples | star rating, thumbs, typed correction | rephrase, tool override, abandonment |
| Volume | low | high |
| Noise | low | medium (needs heuristics) |
| Best use | golden eval cases, severity triage | early-warning dashboards, mining candidates |

Rule of thumb: explicit signals are *labels* (use them for evals);
implicit signals are *alarms* (use them to find where to look).

## Closing the loop

```
product usage ──▶ feedback events ──▶ mined golden cases ──▶ regression gate
      ▲                                                        │
      └──────── ship only what passes the gate ◀───────────────┘
```

Each turn of the wheel raises the bar: today's corrections become
tomorrow's regression tests, so quality compounds instead of decaying.
