import configparser
import httpx
from openai import AzureOpenAI
from langchain.chat_models import AzureChatOpenAI

# Load config.ini values
def load_config():
    config = configparser.ConfigParser()
    config.read("config.ini")
    return config

# Return an LLM for use in LangChain (Azure OpenAI)
def get_llm():
    config = load_config()
    return AzureChatOpenAI(
        api_key=config["azure_openai"]["api_key"],
        api_version=config["azure_openai"]["api_version"],
        azure_endpoint=config["azure_openai"]["endpoint"],
        deployment_name=config["gpt_models"]["model_gpt4o"],
        http_client=httpx.Client(verify=False),
        temperature=0
    )
