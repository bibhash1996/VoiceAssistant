import os
from langchain_openai import ChatOpenAI,OpenAIEmbeddings
from dotenv import load_dotenv
# from langchain.vectorstores.astradb import AstraDB
from langchain_astradb import AstraDBVectorStore
from elevenlabs import ElevenLabs
from openai import OpenAI

load_dotenv()


# OpenAI
apiKey = os.getenv("OPENAI_API_KEY")
openai = OpenAI(api_key=apiKey)


embeddings = OpenAIEmbeddings(model="text-embedding-3-small",api_key=apiKey)

llm = ChatOpenAI(api_key=apiKey,model="gpt-4o")

# Vector store
ASTRA_DB_ENDPOINT = os.getenv("ASTRA_DB_ENDPOINT")
ASTRA_DB_APPLICATION_TOKEN = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
ASTRA_DB_COLLECTION = os.getenv("ASTRA_DB_COLLECTION")

# Elevenlabs
elevenLabApiKey = os.getenv("ELEVENLABS_API_KEY")
elevenLabClient =  ElevenLabs(api_key=elevenLabApiKey)


vectorStore =  AstraDBVectorStore(
    collection_name=ASTRA_DB_COLLECTION,
    embedding=embeddings,
    api_endpoint=ASTRA_DB_ENDPOINT,
    token=ASTRA_DB_APPLICATION_TOKEN,
    namespace="default_keyspace", 
    content_field="text",
    # setup_mode=SetupMode.OFF
)



__all__ = ['llm','vectorStore','embeddings',"elevenLabClient","openai"]