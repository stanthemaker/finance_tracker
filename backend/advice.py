import os
import json

_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            import anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                _client = anthropic.Anthropic(api_key=api_key)
        except Exception:
            pass
    return _client


def _ai_advice(summary: dict, history: list[dict], savings_goal: float) -> list[dict]:
    client = _get_client()
    if not client:
        return []

    fmt = lambda n: f"${n:,.2f}"

    history_lines = "\n".join(
        f"- {h['month']}: income {fmt(h['total_income'])}, expenses {fmt(h['total_expense'])}, saved {fmt(h['net_savings'])}"
        for h in history[-3:]
    ) if history else "No prior history available."

    cat_lines = "\n".join(
        f"  {cat}: {fmt(amt)}"
        for cat, amt in sorted(summary["by_category"].items(), key=lambda x: -x[1])
    )

    prompt = f"""You are a personal finance advisor reviewing a monthly statement. Be concise and actionable.

Month: {summary['month']}
Savings goal: {fmt(savings_goal)}/month

This month:
- Income: {fmt(summary['total_income'])}
- Expenses: {fmt(summary['total_expense'])}
- Net savings: {fmt(summary['net_savings'])}

Spending by category:
{cat_lines}

Recent history (last 3 months):
{history_lines}

Provide 3–5 short, specific advice items grounded in the actual numbers above.
Respond as a JSON array of objects with keys:
  "type": one of "tip", "warning", "good", "danger"
  "title": 3–6 word headline
  "message": 1–2 sentence detail

Output only the JSON array, no markdown fences, no extra text."""

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        _level_map = {"good": "success", "tip": "info", "warning": "warning", "danger": "danger"}
        items = json.loads(text)
        return [
            {
                "level":   _level_map.get(i.get("type", "tip"), "info"),
                "title":   i.get("title", ""),
                "message": i["message"],
            }
            for i in items
        ]
    except Exception:
        return []


def _rules_advice(summary: dict, history: list[dict], savings_goal: float) -> list[dict]:
    advice = []
    income  = summary.get("total_income", 0)
    expense = summary.get("total_expense", 0)
    net     = summary.get("net_savings", 0)
    by_cat  = summary.get("by_category", {})
    fmt = lambda n: f"${n:,.2f}"

    if savings_goal > 0:
        if net >= savings_goal:
            advice.append({"level": "success", "title": "Savings goal met!",
                "message": f"You saved {fmt(net)} this month, beating your {fmt(savings_goal)} goal by {fmt(net - savings_goal)}."})
        else:
            advice.append({"level": "warning", "title": "Below savings goal",
                "message": f"You're {fmt(savings_goal - net)} short of your {fmt(savings_goal)} monthly savings goal."})

    if income == 0:
        advice.append({"level": "info", "title": "No income detected",
            "message": "No income transactions found this month. Upload your checking statement to track earnings."})

    if income > 0 and expense > income:
        advice.append({"level": "danger", "title": "Spending exceeds income",
            "message": f"You spent {fmt(expense)} but earned {fmt(income)} — deficit of {fmt(expense - income)}."})

    dining = by_cat.get("Dining", 0)
    if expense > 0 and dining / expense > 0.25:
        advice.append({"level": "warning", "title": "High dining spend",
            "message": f"Dining is {dining/expense*100:.0f}% of spending ({fmt(dining)}). Consider cooking at home more."})

    if by_cat:
        top_cat, top_amt = max(by_cat.items(), key=lambda x: x[1])
        if top_cat not in ("Housing", "Transfer", "Payment", "Investment") and expense > 0:
            advice.append({"level": "info", "title": f"Top category: {top_cat}",
                "message": f"Your largest expense is {top_cat} at {fmt(top_amt)} ({top_amt/expense*100:.0f}% of expenses)."})

    if len(history) >= 2:
        recent = [h.get("net_savings", 0) for h in history[-2:]]
        if net > recent[-1] > recent[-2]:
            advice.append({"level": "success", "title": "Savings trending up",
                "message": "Net savings have increased 3 months in a row — great momentum!"})

    return advice


def generate_advice(summary: dict, history: list[dict], savings_goal: float) -> dict:
    items = _ai_advice(summary, history, savings_goal)
    ai_powered = bool(items)
    if not items:
        items = _rules_advice(summary, history, savings_goal)

    return {
        "month":        summary["month"],
        "savings_goal": savings_goal,
        "net_savings":  summary["net_savings"],
        "advice":       items,
        "ai_powered":   ai_powered,
    }
