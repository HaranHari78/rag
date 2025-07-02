import pandas as pd
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from util import *
from langchain_community.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings
from config import *

csv_path = "d2c1f46e2b3267d315fb03f76724aa7036ea01b3f1803e94126e26dc26881629.csv"
df = pd.read_csv(csv_path)

# --- Create documents ---
documents = []
for _, row in tqdm(df.iterrows(), total=len(df)):
    if pd.isna(row["text"]):
        continue
    documents.append(Document(page_content=row["text"], metadata={"source": row["title"]}))

splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(documents)

batches = list(batchify(chunks, 20))


# --- Embedding & FAISS index ---
embedding_model = AzureOpenAIEmbeddings(
    deployment=config["embedding_models"]["text_embedding_3_large"],
    model="text-embedding-3-large",
    openai_api_key=config["azure_openai"]["api_key"],
    azure_endpoint=config["azure_openai"]["endpoint"],
    openai_api_version=config["azure_openai_4O"]["api_version"],
    chunk_size=1000
)

def build_faiss(batch):
    return FAISS.from_documents(batch, embedding_model)

sub_indexes = []
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(build_faiss, batch): batch for batch in batches}
    for future in tqdm(as_completed(futures), total=len(futures)):
        try:
            sub_indexes.append(future.result())
        except Exception as e:
            print(f"Batch failed: {e}")

# Merge all sub-indexes into one
print("Merging FAISS indexes...")
main_index = sub_indexes[0]
for sub_index in sub_indexes[1:]:
    main_index.merge_from(sub_index)

# Save final FAISS index
print("Saving FAISS index...")
main_index.save_local("faiss_index")