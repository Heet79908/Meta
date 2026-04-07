"""
Task registry for SQL Data Analysis OpenEnv.

Each task has:
  id          – unique string
  difficulty  – easy / medium / hard
  description – shown to the agent
  hint        – optional nudge
  grader      – fn(result, sql_query, steps) -> (reward: float, feedback: str, done: bool)
"""

import re


# ─── Grader helpers ──────────────────────────────────────────────────────────

def _has_error(result: dict) -> bool:
    return bool(result.get("error"))

def _rows(result: dict) -> list:
    return result.get("rows", [])

def _cols(result: dict) -> list[str]:
    return [c.lower() for c in result.get("columns", [])]

def _has_col(cols: list[str], keywords: list[str]) -> bool:
    """Return True if any column name contains any of the given keywords."""
    return any(kw in col for col in cols for kw in keywords)


# ─── Task 1 – EASY ───────────────────────────────────────────────────────────
# Find the total salary bill per department, ordered highest first.

def grade_task1(result: dict, sql: str, steps: int) -> tuple[float, str, bool]:
    if _has_error(result):
        return 0.0, f"SQL error: {result['error']}", False

    rows = _rows(result)
    cols = _cols(result)

    if not rows:
        return 0.1, "Query ran but returned no rows. Check your JOIN and GROUP BY.", False

    # Must have dept name + salary total
    has_dept   = _has_col(cols, ["name", "department", "dept"])
    has_salary = _has_col(cols, ["salary", "total", "sum"])

    if not has_dept:
        return 0.2, "Result must include the department name.", False
    if not has_salary:
        return 0.3, "Result must include the total salary for each department.", False

    # Check ordering (highest first)
    salary_col = next((c for c in _cols(result) if "salary" in c or "total" in c or "sum" in c), None)
    if salary_col and len(rows) > 1:
        vals = [r.get(salary_col) or r.get(salary_col.upper()) for r in rows]
        try:
            vals = [float(v) for v in vals if v is not None]
            ordered = vals == sorted(vals, reverse=True)
            if not ordered:
                return 0.6, "Correct columns, but result is not ordered highest-first.", False
        except (TypeError, ValueError):
            pass

    # Must return all 5 departments
    if len(rows) < 5:
        return 0.7, f"Expected 5 department rows, got {len(rows)}.", False

    step_bonus = max(0.0, (10 - steps) / 10 * 0.1)
    return min(1.0, 0.9 + step_bonus), "Correct! Salary totals per department, ordered descending.", True


# ─── Task 2 – MEDIUM ─────────────────────────────────────────────────────────
# Find the top-3 customers by total order value (completed orders only).

def grade_task2(result: dict, sql: str, steps: int) -> tuple[float, str, bool]:
    if _has_error(result):
        return 0.0, f"SQL error: {result['error']}", False

    rows = _rows(result)
    cols = _cols(result)

    if not rows:
        return 0.1, "Query returned no rows. Are you filtering on status='completed'?", False

    has_customer = _has_col(cols, ["name", "customer"])
    has_total    = _has_col(cols, ["total", "amount", "sum", "revenue", "value"])

    if not has_customer:
        return 0.2, "Include the customer name in your result.", False
    if not has_total:
        return 0.3, "Include the total order value per customer.", False

    # Must be exactly top-3
    if len(rows) > 3:
        return 0.5, f"Return only the top 3 customers (got {len(rows)}).", False
    if len(rows) < 3:
        return 0.4, f"Expected 3 rows, got {len(rows)}. Check your LIMIT / data filter.", False

    # Verify completed filter was used
    if "complet" not in sql.lower():
        return 0.6, "You must filter for completed orders only (status = 'completed').", False

    # Check ordering
    total_col = next((c for c in _cols(result)
                      if any(k in c for k in ["total", "amount", "sum", "revenue"])), None)
    if total_col and len(rows) > 1:
        vals = [rows[i].get(total_col) for i in range(len(rows))]
        try:
            vals = [float(v) for v in vals if v is not None]
            if vals != sorted(vals, reverse=True):
                return 0.7, "Order by total value descending.", False
        except (TypeError, ValueError):
            pass

    step_bonus = max(0.0, (10 - steps) / 10 * 0.1)
    return min(1.0, 0.9 + step_bonus), "Correct! Top 3 customers by completed order value.", True


# ─── Task 3 – HARD ───────────────────────────────────────────────────────────
# For each product category, find the month with the highest total sales amount
# and include the month's total, using window functions or subqueries.

def grade_task3(result: dict, sql: str, steps: int) -> tuple[float, str, bool]:
    if _has_error(result):
        return 0.0, f"SQL error: {result['error']}", False

    rows = _rows(result)
    cols = _cols(result)

    if not rows:
        return 0.1, "No rows returned. Check your joins and grouping.", False

    has_category = _has_col(cols, ["category", "cat"])
    has_month    = _has_col(cols, ["month", "period", "strftime", "date"])
    has_total    = _has_col(cols, ["total", "amount", "sales", "sum"])

    if not has_category:
        return 0.2, "Include product category in the result.", False
    if not has_month:
        return 0.3, "Include the month in the result.", False
    if not has_total:
        return 0.4, "Include the sales total for the best month.", False

    # Should have one row per category (products table has 2 categories)
    category_col = next((c for c in _cols(result) if "cat" in c), None)
    if category_col:
        categories = {str(r.get(category_col, r.get("category", ""))) for r in rows}
        if len(categories) < 2:
            return 0.5, "Result should cover multiple product categories.", False

    # Reward for using advanced SQL (window functions / subquery / CTE)
    advanced = any(k in sql.lower() for k in ["rank()", "row_number()", "dense_rank()",
                                                "partition by", "with ", "having"])
    base = 0.85 if advanced else 0.75

    step_bonus = max(0.0, (10 - steps) / 10 * 0.1)
    feedback = ("Excellent! Best-month per category identified" +
                (" using advanced SQL." if advanced else "."))
    return min(1.0, base + step_bonus), feedback, True


# ─── Registry ─────────────────────────────────────────────────────────────────

TASKS = [
    {
        "id": "task_easy_dept_salary",
        "difficulty": "easy",
        "description": (
            "Calculate the total salary expense per department. "
            "Return department name and total salary, ordered from highest to lowest."
        ),
        "hint": "JOIN employees with departments, GROUP BY department, ORDER BY total DESC.",
        "grader": grade_task1,
    },
    {
        "id": "task_medium_top_customers",
        "difficulty": "medium",
        "description": (
            "Find the top 3 customers by total spending on COMPLETED orders only. "
            "Return customer name and their total order value, ordered highest first."
        ),
        "hint": "JOIN orders with customers, filter status='completed', GROUP BY customer, ORDER BY total DESC, LIMIT 3.",
        "grader": grade_task2,
    },
    {
        "id": "task_hard_best_month_by_category",
        "difficulty": "hard",
        "description": (
            "For each product category, identify the calendar month (YYYY-MM) with the "
            "highest total sales amount. Return category, best month, and that month's total sales."
        ),
        "hint": "JOIN sales → products, group by category + month, then find the max month per category (use a subquery, CTE, or window function).",
        "grader": grade_task3,
    },
]
