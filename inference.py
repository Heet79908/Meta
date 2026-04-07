"""
inference.py  –  SQL Data Analysis OpenEnv
Runs the agent against all 3 tasks and emits structured stdout logs.

Required env vars:
  API_BASE_URL   LLM API base URL
  MODEL_NAME     Model identifier
  HF_TOKEN       Hugging Face / API key
"""

import os
import sys
import json
import time
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME   = os.environ.get("MODEL_NAME",   "gpt-4o-mini")
HF_TOKEN     = os.environ.get("HF_TOKEN",     "")
ENV_URL      = os.environ.get("ENV_URL",       "http://localhost:7860")

client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN or "sk-placeholder")

MAX_STEPS = 8  # budget per task

# ── Logging helpers (required format) ─────────────────────────────────────────

def log_start(task_id: str, task_description: str):
    print(json.dumps({
        "type":             "[START]",
        "task_id":          task_id,
        "task_description": task_description,
        "model":            MODEL_NAME,
        "timestamp":        time.time(),
    }), flush=True)

def log_step(task_id: str, step: int, action: dict, observation: dict,
             reward: float, done: bool):
    print(json.dumps({
        "type":        "[STEP]",
        "task_id":     task_id,
        "step":        step,
        "action":      action,
        "observation": observation,
        "reward":      reward,
        "done":        done,
        "timestamp":   time.time(),
    }), flush=True)

def log_end(task_id: str, total_steps: int, final_reward: float, success: bool):
    print(json.dumps({
        "type":         "[END]",
        "task_id":      task_id,
        "total_steps":  total_steps,
        "final_reward": final_reward,
        "success":      success,
        "timestamp":    time.time(),
    }), flush=True)

# ── Environment helpers ────────────────────────────────────────────────────────

def env_reset(task_id: str) -> dict:
    r = requests.post(f"{ENV_URL}/reset", json={"task_id": task_id}, timeout=30)
    r.raise_for_status()
    return r.json()

def env_step(session_id: str, sql: str) -> dict:
    r = requests.post(f"{ENV_URL}/step",
                      json={"session_id": session_id, "action": {"sql": sql}},
                      timeout=30)
    r.raise_for_status()
    return r.json()

def env_tasks() -> list:
    r = requests.get(f"{ENV_URL}/tasks", timeout=15)
    r.raise_for_status()
    return r.json()

# ── LLM agent ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert SQL analyst. 
You are given access to a SQLite database. Your job is to write a single correct SELECT query 
to answer the task. 

Rules:
- Only write a raw SQL query. No markdown, no explanation.
- Only SELECT statements are allowed.
- Use the exact table/column names from the schema.
- If you receive feedback, fix your query accordingly.
"""

def build_user_message(task_desc: str, schema: str, history: list[dict]) -> str:
    history_txt = ""
    for h in history[-3:]:  # last 3 attempts for context
        history_txt += f"\nAttempt {h['step']}:\nSQL: {h['sql']}\nFeedback: {h['feedback']}\nReward: {h['reward']}\n"

    return f"""Task: {task_desc}

Schema:
{schema}

{('Previous attempts:' + history_txt) if history_txt else 'This is your first attempt.'}

Write the correct SQL query now."""

def ask_llm(task_desc: str, schema: str, history: list[dict]) -> str:
    user_msg = build_user_message(task_desc, schema, history)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.1,
        max_tokens=512,
    )
    sql = response.choices[0].message.content.strip()
    # Strip any accidental markdown fences
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql

# ── Main loop ─────────────────────────────────────────────────────────────────

def run_task(task: dict) -> float:
    task_id   = task["id"]
    task_desc = task["description"]

    reset_resp   = env_reset(task_id)
    session_id   = reset_resp["session_id"]
    schema       = reset_resp.get("schema", "")
    
    log_start(task_id, task_desc)

    history      = []
    final_reward = 0.0
    step         = 0

    for step in range(1, MAX_STEPS + 1):
        sql = ask_llm(task_desc, schema, history)
        
        step_resp  = env_step(session_id, sql)
        obs        = step_resp.get("observation", {})
        reward     = step_resp.get("reward", 0.0)
        done       = step_resp.get("done", False)
        feedback   = obs.get("feedback", "")

        log_step(task_id, step, {"sql": sql}, obs, reward, done)

        history.append({"step": step, "sql": sql, "feedback": feedback, "reward": reward})
        final_reward = reward

        if done:
            break

    success = final_reward >= 0.8
    log_end(task_id, step, final_reward, success)
    return final_reward


def main():
    print(f"Connecting to environment at {ENV_URL} ...", flush=True)

    # Health check
    try:
        h = requests.get(f"{ENV_URL}/health", timeout=15)
        h.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Cannot reach environment: {e}")
        sys.exit(1)

    tasks = env_tasks()
    print(f"Found {len(tasks)} tasks: {[t['id'] for t in tasks]}\n", flush=True)

    results = {}
    for task in tasks:
        reward = run_task(task)
        results[task["id"]] = reward
        print(f"  ✓ {task['id']} → reward={reward:.3f}\n", flush=True)

    print("\n=== Final Scores ===")
    for tid, r in results.items():
        print(f"  {tid}: {r:.3f}")
    avg = sum(results.values()) / len(results) if results else 0.0
    print(f"  AVERAGE: {avg:.3f}")


if __name__ == "__main__":
    main()
