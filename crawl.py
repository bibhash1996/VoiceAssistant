import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document


import os
from langchain_openai import ChatOpenAI,OpenAIEmbeddings
from dotenv import load_dotenv
# from langchain.vectorstores.astradb import AstraDB
from langchain_astradb import AstraDBVectorStore
from langchain_astradb.utils.astradb import SetupMode

load_dotenv()


# OpenAI
apiKey = os.getenv("OPENAI_API_KEY")
embeddings = OpenAIEmbeddings(model="text-embedding-3-small",api_key=apiKey)

llm = ChatOpenAI(api_key=apiKey,model="gpt-4o")

# Vector store
ASTRA_DB_ENDPOINT = os.getenv("ASTRA_DB_ENDPOINT")
ASTRA_DB_APPLICATION_TOKEN = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
ASTRA_DB_COLLECTION = os.getenv("ASTRA_DB_COLLECTION")



vectorStore =  AstraDBVectorStore(
    collection_name=ASTRA_DB_COLLECTION,
    embedding=embeddings,
    api_endpoint=ASTRA_DB_ENDPOINT,
    token=ASTRA_DB_APPLICATION_TOKEN,
    namespace="default_keyspace", 
    content_field="text",
    # setup_mode=SetupMode.OFF
)

visited = set()

def crawl_website(base_url, max_pages=10):
    to_visit = [base_url]
    all_docs = []

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            response = requests.get(url, timeout=5)
            if 'text/html' not in response.headers['Content-Type']:
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            text = soup.get_text(separator="\n", strip=True)

            doc = Document(page_content=text, metadata={"source": url})
            all_docs.append(doc)

            for link_tag in soup.find_all("a", href=True):
                link = urljoin(url, link_tag['href'])
                if urlparse(link).netloc == urlparse(base_url).netloc:
                    to_visit.append(link)

        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
    
    return all_docs


# 🌐 Start crawling
base_url = "https://bibhash.xyz"  # change this to your target site
docs = crawl_website(base_url,50)

# print(len(docs))

# 🧩 Split content
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
split_docs = splitter.split_documents(docs)


vectorStore.add_documents(split_docs)

print("Added")



