import os
import re
import json
import pandas as pd
import configparser
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI

# Load config.ini
config = configparser.ConfigParser()
config.read("config.ini")

# Azure credentials
AZURE_OPENAI_API_KEY = config["azure_openai"]["api_key"]
AZURE_OPENAI_ENDPOINT = config["azure_openai"]["endpoint"]
AZURE_OPENAI_API_VERSION = config["azure_openai"]["api_version"]
EMBEDDING_DEPLOYMENT = config["embedding_models"]["text_embedding_3_large"]
EMBEDDING_MODEL = "text-embedding-3-large"
GPT_DEPLOYMENT = config["gpt_models"]["model_gpt4o"]

# Util functions
def parse_llm_json(raw_text: str) -> str:
    pattern = r"```(?:json)?\s*(.*?)```"
    match = re.search(pattern, raw_text, flags=re.DOTALL)
    raw_text = match.group(1).strip() if match else raw_text.strip()
    if raw_text.startswith("json"):
        raw_text = raw_text[len("json"):].strip()
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        fixed = raw_text.replace("'", '"')
        parsed = json.loads(fixed)
    return json.dumps(parsed)

def normalize_text(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# Load dataset
csv_path = "d2c1f46e2b3267d315fb03f76724aa7036ea01b3f1803e94126e26dc26881629.csv"
df = pd.read_csv(csv_path)

# Grouped chunks per document
splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=500)
grouped_batches = []
for _, row in tqdm(df.iterrows(), total=len(df)):
    if pd.isna(row["text"]):
        continue
    source = row["title"]
    chunks = splitter.split_text(row["text"])
    doc_chunks = [Document(page_content=chunk, metadata={"source": source}) for chunk in chunks]
    if doc_chunks:
        grouped_batches.append(doc_chunks)

# Embedding model
embedding_model = AzureOpenAIEmbeddings(
    deployment=EMBEDDING_DEPLOYMENT,
    model=EMBEDDING_MODEL,
    openai_api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    openai_api_version=AZURE_OPENAI_API_VERSION,
    chunk_size=1000
)

# Build FAISS index
def build_faiss(batch):
    return FAISS.from_documents(batch, embedding_model)

sub_indexes = []
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(build_faiss, batch): batch for batch in grouped_batches}
    for future in tqdm(as_completed(futures), total=len(futures)):
        try:
            sub_indexes.append(future.result())
        except Exception as e:
            print(f"Batch failed: {e}")

main_index = sub_indexes[0]
for sub_index in sub_indexes[1:]:
    main_index.merge_from(sub_index)
main_index.save_local("faiss_index")

# Vector DB Search
vectorstore = FAISS.load_local("faiss_index", embeddings=embedding_model, allow_dangerous_deserialization=True)
query = "Extract the patient's kappa free light chain (mg/L), lambda free light chain (mg/L), and kappa/lambda ratio, along with the lab date and evidence."
results = vectorstore.similarity_search(query, k=1000)

# Filter matching content
filtered_chunks = []
for doc in results:
    norm_text = normalize_text(doc.page_content)
    source_title = doc.metadata.get("source", "Unknown")
    if source_title != "Unknown" and ('kappa' in norm_text or 'lambda' in norm_text or 'ratio' in norm_text):
        filtered_chunks.append({"title": source_title, "content": doc.page_content})

# Regroup filtered chunks per doc
grouped_filtered = {}
for chunk in filtered_chunks:
    grouped_filtered.setdefault(chunk["title"], []).append(chunk["content"])

# Setup LLM
llm = AzureChatOpenAI(
    deployment_name=GPT_DEPLOYMENT,
    model_name="gpt-4o",
    openai_api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    openai_api_version=AZURE_OPENAI_API_VERSION,
    temperature=0
)

# Run LLM
final_results = []
for i, (doc_title, chunks) in enumerate(grouped_filtered.items()):
    json_context = [{"note_id": j + 1, "title": doc_title, "content": chunk} for j, chunk in enumerate(chunks)]

    full_prompt = f"""
You are a medical information extraction assistant. Your task is to extract lab results from clinical notes.

Your goal is to extract the following values, **only from the given document context**, and **strictly ignore or skip the document** if:
- You are unsure where the values come from.
- The values appear to be duplicated from a different unrelated document.
- The document contains no lab results.

Extract these fields only if they are clearly present in the current context:
- ✅ **Kappa free light chains** (must have numeric value and unit, e.g., 1.35 mg/dL, <0.15 mg/dL)
- ✅ **Lambda free light chains** (must have numeric value and unit)
- ✅ **Kappa/Lambda ratio** (numeric ratio, may include < or > symbols)
- ✅ **Lab test date** (clearly stated; if partial date like year/month, format as YYYY-MM-XX or YYYY-XX-XX)
- ✅ **Supporting evidence sentences** (must include the above values in the same sentence or logically linked)

⚠️ **Important Constraints:**
- Do NOT hallucinate values or infer them from vague summaries.
- Do NOT use values that are not clearly tied to this specific document context.
- If the extracted values appear copied from another unrelated document, discard the entire output for this document.
- Do NOT include diagnosis phrases like "monoclonal kappa detected" unless a real numeric value is stated.
- Do NOT reuse values from one document in another.
- If the values (kappa, lambda, or ratio) are not explicitly present in the context of THIS document, skip them.
- This context may contain overlapping content between chunks. If a value appears multiple times due to repetition, only extract it once.


✅ Proceed only if the lab values are explicitly mentioned with units.

Respond in strict JSON format like this:
[
  {{
    "kappa_flc": "...",
    "lambda_flc": "...",
    "kappa_lambda_ratio": "...",
    "date_of_lab": "...",
    "evidence_sentences": ["...", "..."]
  }}
]

--- Context:
{json.dumps(json_context, indent=2)}
"""

    try:
        print(f"🧠 Running batch {i+1}/{len(grouped_filtered)}...")
        response = llm.invoke(full_prompt)
        cleaned = parse_llm_json(response.content)
        batch_result = json.loads(cleaned)

        for item in batch_result:
            item["source_document"] = doc_title
            item["context"] = json.dumps(item, indent=2)
        final_results.extend(batch_result)
    except Exception as e:
        print(f"❌ Failed batch {i+1}: {e}")

# Format & Save
for row in final_results:
    if isinstance(row.get("evidence_sentences"), list):
        row["evidence_sentences"] = "\n".join(row["evidence_sentences"])

df = pd.DataFrame(final_results)
df = df[["source_document", "kappa_flc", "lambda_flc", "kappa_lambda_ratio", "date_of_lab", "evidence_sentences", "context"]]
df.drop_duplicates(
    subset=["kappa_flc", "lambda_flc", "kappa_lambda_ratio"],
    inplace=True
)

# Save Excel & JSON
output_dir = r"C:\Users\HariharaM12\PycharmProjects\Task2"
os.makedirs(output_dir, exist_ok=True)

excel_path = os.path.join(output_dir, "Output2.xlsx")
json_path = os.path.join(output_dir, "Output2.json")

df.to_excel(excel_path, index=False)
df.to_json(json_path, orient="records", indent=2)

print(f"\n✅ Excel saved: {excel_path}")
print(f"✅ JSON saved: {json_path}")
