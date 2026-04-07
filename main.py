import sqlite3
import json
import uuid
import os
import re
from typing import Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
from tasks.task_registry import TASKS

import tempfile
DB_PATH = os.path.join(tempfile.gettempdir(), "openenv_sql.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Create tables with realistic data
    cursor.executescript("""
    DROP TABLE IF EXISTS employees;
    DROP TABLE IF EXISTS departments;
    DROP TABLE IF EXISTS orders;
    DROP TABLE IF EXISTS products;
    DROP TABLE IF EXISTS customers;
    DROP TABLE IF EXISTS sales;

    CREATE TABLE departments (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        budget REAL,
        location TEXT
    );

    CREATE TABLE employees (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        department_id INTEGER,
        salary REAL,
        hire_date TEXT,
        manager_id INTEGER,
        FOREIGN KEY (department_id) REFERENCES departments(id)
    );

    CREATE TABLE customers (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT,
        city TEXT,
        country TEXT,
        created_at TEXT
    );

    CREATE TABLE products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT,
        price REAL,
        stock INTEGER
    );

    CREATE TABLE orders (
        id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        product_id INTEGER,
        quantity INTEGER,
        order_date TEXT,
        status TEXT,
        total_amount REAL,
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    );

    CREATE TABLE sales (
        id INTEGER PRIMARY KEY,
        product_id INTEGER,
        amount REAL,
        sale_date TEXT,
        region TEXT,
        FOREIGN KEY (product_id) REFERENCES products(id)
    );

    INSERT INTO departments VALUES
        (1, 'Engineering', 500000, 'New York'),
        (2, 'Marketing', 200000, 'San Francisco'),
        (3, 'Sales', 300000, 'Chicago'),
        (4, 'HR', 150000, 'New York'),
        (5, 'Finance', 250000, 'Boston');

    INSERT INTO employees VALUES
        (1,  'Alice Johnson',   1, 95000,  '2019-03-15', NULL),
        (2,  'Bob Smith',       1, 82000,  '2020-07-01', 1),
        (3,  'Carol White',     2, 75000,  '2018-11-20', NULL),
        (4,  'David Lee',       3, 68000,  '2021-01-10', NULL),
        (5,  'Eva Martinez',    1, 91000,  '2019-06-05', 1),
        (6,  'Frank Brown',     4, 62000,  '2022-03-22', NULL),
        (7,  'Grace Kim',       2, 78000,  '2020-09-15', 3),
        (8,  'Henry Davis',     3, 72000,  '2019-12-01', 4),
        (9,  'Iris Wilson',     5, 88000,  '2018-05-30', NULL),
        (10, 'Jack Taylor',     1, 76000,  '2021-08-14', 1),
        (11, 'Karen Anderson',  3, 65000,  '2022-01-05', 4),
        (12, 'Liam Thomas',     2, 71000,  '2020-04-20', 3);

    INSERT INTO customers VALUES
        (1,  'Acme Corp',       'acme@example.com',    'New York',     'USA',    '2020-01-15'),
        (2,  'Beta LLC',        'beta@example.com',    'London',       'UK',     '2020-03-22'),
        (3,  'Gamma Inc',       'gamma@example.com',   'Toronto',      'Canada', '2021-06-10'),
        (4,  'Delta Co',        'delta@example.com',   'Sydney',       'Australia','2019-11-05'),
        (5,  'Epsilon Ltd',     'eps@example.com',     'Berlin',       'Germany','2022-02-28'),
        (6,  'Zeta Partners',   'zeta@example.com',    'New York',     'USA',    '2021-07-14'),
        (7,  'Eta Solutions',   'eta@example.com',     'Chicago',      'USA',    '2020-09-01'),
        (8,  'Theta Global',    'theta@example.com',   'Paris',        'France', '2022-04-18');

    INSERT INTO products VALUES
        (1,  'Laptop Pro',       'Electronics', 1299.99, 50),
        (2,  'Wireless Mouse',   'Electronics',   29.99, 200),
        (3,  'Standing Desk',    'Furniture',    549.99,  30),
        (4,  'Office Chair',     'Furniture',    399.99,  45),
        (5,  'Monitor 27"',      'Electronics',  349.99,  60),
        (6,  'Keyboard Mech',    'Electronics',   89.99, 150),
        (7,  'Webcam HD',        'Electronics',   79.99, 100),
        (8,  'Desk Lamp',        'Furniture',     49.99,  80);

    INSERT INTO orders VALUES
        (1,  1, 1, 2, '2023-01-10', 'completed', 2599.98),
        (2,  2, 3, 1, '2023-01-15', 'completed',  549.99),
        (3,  3, 5, 3, '2023-02-01', 'completed', 1049.97),
        (4,  1, 2, 5, '2023-02-10', 'completed',  149.95),
        (5,  4, 4, 2, '2023-02-20', 'completed',  799.98),
        (6,  5, 1, 1, '2023-03-05', 'completed', 1299.99),
        (7,  6, 6, 3, '2023-03-10', 'pending',    269.97),
        (8,  7, 7, 2, '2023-03-15', 'completed',  159.98),
        (9,  8, 8, 4, '2023-04-01', 'completed',  199.96),
        (10, 2, 5, 1, '2023-04-05', 'cancelled',  349.99),
        (11, 3, 2, 10,'2023-04-10', 'completed',  299.90),
        (12, 1, 4, 1, '2023-04-15', 'pending',    399.99);

    INSERT INTO sales VALUES
        (1,  1, 15000.00, '2023-01-10', 'North'),
        (2,  2,  3500.00, '2023-01-15', 'South'),
        (3,  3,  8000.00, '2023-02-01', 'East'),
        (4,  5, 12000.00, '2023-02-10', 'West'),
        (5,  1, 22000.00, '2023-02-20', 'North'),
        (6,  4,  9500.00, '2023-03-05', 'South'),
        (7,  6,  4200.00, '2023-03-10', 'East'),
        (8,  7,  6800.00, '2023-03-15', 'West'),
        (9,  2,  2100.00, '2023-04-01', 'North'),
        (10, 5, 18000.00, '2023-04-05', 'South'),
        (11, 1, 30000.00, '2023-04-10', 'East'),
        (12, 3, 11000.00, '2023-04-15', 'West');
    """)

    conn.commit()
    conn.close()

sessions: dict[str, dict] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="SQL Data Analysis OpenEnv", lifespan=lifespan)

# ── Models ────────────────────────────────────────────────────────────────────

class ResetRequest(BaseModel):
    task_id: str | None = None

class StepRequest(BaseModel):
    session_id: str
    action: dict[str, Any]

class StateRequest(BaseModel):
    session_id: str

# ── Helpers ───────────────────────────────────────────────────────────────────

def execute_sql(query: str) -> dict:
    """Execute a SQL query safely and return results."""
    # Basic safety: only allow SELECT statements
    clean = query.strip().upper()
    if not clean.startswith("SELECT") and not clean.startswith("WITH"):
        return {"error": "Only SELECT queries are allowed.", "rows": [], "columns": []}
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(query)
        rows = [dict(row) for row in cursor.fetchall()]
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        conn.close()
        return {"rows": rows, "columns": columns, "row_count": len(rows)}
    except Exception as e:
        return {"error": str(e), "rows": [], "columns": []}

def get_schema() -> str:
    return """
Tables available:
  departments(id, name, budget, location)
  employees(id, name, department_id, salary, hire_date, manager_id)
  customers(id, name, email, city, country, created_at)
  products(id, name, category, price, stock)
  orders(id, customer_id, product_id, quantity, order_date, status, total_amount)
  sales(id, product_id, amount, sale_date, region)
""".strip()

# ── OpenEnv API ────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "env": "SQL Data Analysis OpenEnv"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/reset")
def reset(req: ResetRequest = None):
    task_id = (req.task_id if req else None) or TASKS[0]["id"]
    task = next((t for t in TASKS if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "task_id": task_id,
        "steps": 0,
        "max_steps": 10,
        "done": False,
        "last_result": None,
        "reward": 0.0,
    }

    return {
        "session_id": session_id,
        "task_id": task_id,
        "task_description": task["description"],
        "schema": get_schema(),
        "observation": {
            "task": task["description"],
            "hint": task.get("hint", ""),
            "schema": get_schema(),
            "steps_remaining": 10,
        },
        "done": False,
        "reward": 0.0,
        "info": {},
    }

@app.post("/step")
def step(req: StepRequest):
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["done"]:
        raise HTTPException(status_code=400, detail="Episode already done. Call /reset.")

    session["steps"] += 1
    action = req.action
    sql_query = action.get("sql", "").strip()

    if not sql_query:
        return {
            "session_id": req.session_id,
            "observation": {"error": "No SQL query provided", "result": None},
            "reward": 0.0,
            "done": False,
            "info": {"steps": session["steps"]},
        }

    result = execute_sql(sql_query)
    session["last_result"] = result

    # Grade the result
    task_id = session["task_id"]
    task = next(t for t in TASKS if t["id"] == task_id)
    reward, feedback, done = task["grader"](result, sql_query, session["steps"])

    session["reward"] = reward
    if done or session["steps"] >= session["max_steps"]:
        session["done"] = True

    return {
        "session_id": req.session_id,
        "observation": {
            "result": result,
            "feedback": feedback,
            "steps_remaining": session["max_steps"] - session["steps"],
        },
        "reward": reward,
        "done": session["done"],
        "info": {"steps": session["steps"], "task_id": task_id},
    }

@app.get("/state")
def state(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    task = next(t for t in TASKS if t["id"] == session["task_id"])
    return {
        "session_id": session_id,
        "task_id": session["task_id"],
        "task_description": task["description"],
        "schema": get_schema(),
        "steps": session["steps"],
        "max_steps": session["max_steps"],
        "done": session["done"],
        "reward": session["reward"],
        "last_result": session["last_result"],
    }

@app.get("/tasks")
def list_tasks():
    return [
        {"id": t["id"], "difficulty": t["difficulty"], "description": t["description"]}
        for t in TASKS
    ]
