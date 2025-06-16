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
 
