[azure_openai]
api_key = 8804263e0e884a73b493a58f22505cc6
endpoint = https://omh-eus-2-test-01.openai.azure.com/
api_version = 2024-02-01

[gpt_models]
model_gpt4o = OMH-EUS2-GPT4O-1

https://chatgpt.com/share/684fe21e-4d20-8007-9508-17a1cc08f1e4

endpoint = "https://omh-eus-2-test-01.openai.azure.com/"

model_name = "text-embedding-3-large"

deployment = "text-embedding-3-large-EUS-2-01"
 
8804263e0e884a73b493a58f22505cc6
 
endpoint = "https://omh-eus-2-test-01.openai.azure.com/"

model_name = "text-embedding-3-large"

deployment = "text-embedding-3-large-EUS-2-01"
 
api_version = "2024-02-01"
 
client = AzureOpenAI(

    api_version="2024-12-01-preview",

    endpoint=endpoint,

    credential=AzureKeyCredential("<API_KEY>")

)


import pandas as pd
from langchain.embeddings import AzureOpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.text_splitter import CharacterTextSplitter
from langchain.docstore.document import Document
from langchain.chat_models import AzureChatOpenAI
from langchain.chains import RetrievalQA

# --- Azure OpenAI Embedding & Chat Model Configuration ---
AZURE_OPENAI_ENDPOINT = "https://<your-endpoint>.openai.azure.com/"
AZURE_OPENAI_API_KEY = "<your-api-key>"
DEPLOYMENT_NAME_EMBEDDING = "TEXT-EMB-3-LARGE"
DEPLOYMENT_NAME_CHAT = "GPT4-DEPLOYMENT"

# --- Load CSV ---
df = pd.read_csv("your_data.csv")
text_column = "text"  # Replace with the actual column name
texts = df[text_column].dropna().tolist()

# --- Convert to LangChain Documents ---
documents = [Document(page_content=text) for text in texts]

# --- Split if needed ---
splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
docs = splitter.split_documents(documents)

# --- Create Embeddings ---
embedding = AzureOpenAIEmbeddings(
    deployment=DEPLOYMENT_NAME_EMBEDDING,
    model="text-embedding-3-large",
    openai_api_version="2024-12-01-preview",
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    openai_api_key=AZURE_OPENAI_API_KEY,
)

# --- Create FAISS Vector Store ---
vectorstore = FAISS.from_documents(docs, embedding)
vectorstore.save_local("faiss_index")

# --- Load FAISS and Create QA Chain ---
retriever = vectorstore.as_retriever()

llm = AzureChatOpenAI(
    deployment_name=DEPLOYMENT_NAME_CHAT,
    model_name="gpt-4",  # or gpt-35-turbo
    openai_api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    openai_api_version="2024-12-01-preview",
    temperature=0,
)

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever,
    return_source_documents=True
)

# --- Example Query ---
query = "What does the document say about patient diagnosis?"
result = qa_chain({"query": query})

print("Answer:", result["result"])
print("Sources:", [doc.metadata for doc in result["source_documents"]])
 
