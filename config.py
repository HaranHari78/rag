from dotenv import load_dotenv
import os

load_dotenv()
config = {
    "azure_openai_4O": {
        "api_version": os.environ.get("AZURE_OPENAI_API_VERSION_4O"),
        "model": os.environ.get("MODEL_4O"),
        "deployment": os.environ.get("DEPLOYMENT_4O")
    },
    "azure_openai_4_1_mini": {
        "api_version": os.environ.get("AZURE_OPENAI_API_VERSION_4_1_MINI"),
        "model": os.environ.get("MODEL_4_1_MINI"),
        "deployment": os.environ.get("DEPLOYMENT_4_1_MINI")
    },
    "embedding_models": {
        "text_embedding_3_large": os.environ.get("TEXT_EMBEDDING_3_LARGE")
    },
    "azure_openai": {
        "api_key": os.environ.get("AZURE_OPENAI_API_KEY"),
        "endpoint": os.environ.get("AZURE_OPENAI_ENDPOINT")
    }
}