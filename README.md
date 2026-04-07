---
title: SQL Data Analysis OpenEnv
emoji: 🗄️
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 7860
---

# SQL Data Analysis — OpenEnv Environment

A real-world **SQL data analysis** environment for the OpenEnv hackathon.  
An AI agent writes `SELECT` queries to solve progressively harder business-intelligence tasks over a realistic corporate SQLite database.

---

## Environment Description

The environment seeds a SQLite database on startup with six tables modelling a small company:

| Table | Description |
|---|---|
| `departments` | 5 departments with budget and location |
| `employees` | 12 employees with salary, hire date, manager |
| `customers` | 8 business customers across multiple countries |
| `products` | 8 products in 2 categories |
| `orders` | 12 orders with status and total amount |
| `sales` | 12 sales records by region and date |

---

## Tasks

| ID | Difficulty | Description |
|---|---|---|
| `task_easy_dept_salary` | 🟢 Easy | Total salary per department, ordered highest first |
| `task_medium_top_customers` | 🟡 Medium | Top 3 customers by completed-order spend |
| `task_hard_best_month_by_category` | 🔴 Hard | Best sales month per product category |

### Reward Logic (0.0 – 1.0)
- `0.0` — SQL error
- `0.1–0.4` — Query runs but missing key columns / filters
- `0.5–0.7` — Correct structure, wrong ordering / row count
- `0.8–0.9` — Fully correct answer
- `+0.1 bonus` — Solved in fewer steps (speed bonus)

---

## Action / Observation Spaces

**Action**
```json
{ "sql": "SELECT ..." }
```

**Observation**
```json
{
  "result": {
    "rows":      [{ "name": "Engineering", "total_salary": 344000 }, ...],
    "columns":   ["name", "total_salary"],
    "row_count": 5
  },
  "feedback":         "Correct! Salary totals per department, ordered descending.",
  "steps_remaining":  8
}
```

---

## Setup & Run

### Local (dev)
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 7860
```

### Docker
```bash
docker build -t sql-openenv .
docker run -p 7860:7860 sql-openenv
```

### Run Inference
```bash
export API_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4o-mini"
export HF_TOKEN="sk-..."
export ENV_URL="http://localhost:7860"
python inference.py
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Health / info |
| `GET` | `/health` | Liveness probe |
| `GET` | `/tasks` | List all tasks |
| `POST` | `/reset` | Start a new episode (`{"task_id": "..."}`) |
| `POST` | `/step` | Execute an action (`{"session_id": "...", "action": {"sql": "..."}}`) |
| `GET` | `/state?session_id=...` | Get current state |

---

## Environment Variables (required for inference)

| Variable | Purpose |
|---|---|
| `API_BASE_URL` | LLM API base URL |
| `MODEL_NAME` | Model identifier |
| `HF_TOKEN` | Hugging Face / API key |
| `ENV_URL` | URL of this running environment (default: `http://localhost:7860`) |
