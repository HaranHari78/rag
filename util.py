import re
import json

def parse_llm_json(raw_text: str) -> str:
    if not raw_text.strip():
        print("⚠️ Warning: Empty LLM response")
        return "[]"

    pattern = r"```(?:json)?\s*(.*?)```"
    match = re.search(pattern, raw_text, flags=re.DOTALL)
    raw_text = match.group(1).strip() if match else raw_text.strip()

    if raw_text.startswith("json"):
        raw_text = raw_text[len("json"):].strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        print("⚠️ JSON decode error, trying to fix quotes")
        fixed = raw_text.replace("'", '"')
        try:
            parsed = json.loads(fixed)
        except Exception as e:
            print("❌ Still failed:", e)
            return "[]"

    return json.dumps(parsed)

def normalize_text(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def clean_numeric(val: str) -> str:
    if not isinstance(val, str):
        return val
    match = re.search(r"[0-9]+\.?[0-9]*", val)
    return match.group(0) if match else ""

def batchify(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]