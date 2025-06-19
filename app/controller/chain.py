from langchain.schema import Document
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    PromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate
    )
from langchain.chains.combine_documents.stuff import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.history_aware_retriever import create_history_aware_retriever
# from langchain.chains import conversational_retrieval
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from app import llm,vectorStore,elevenLabClient,openai
import tempfile
import os
import json
import websockets


messsage_history = dict()


def getAudioForTheText(text:str):
    audio_stream = elevenLabClient.text_to_speech.convert_as_stream(
        text=text,
        voice_id="CwhRBWXzGAHq8TQ4Fs17",
        model_id="eleven_multilingual_v2",
        # format="mp3"
    )
 

    return audio_stream

def getAnswerUsingVectorResult(session_id:str,question:str):
    retriever = vectorStore.as_retriever()
    # docs = retriever.invoke(question)
    # print(docs)
    prompt =  ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template("""
          You are a chatbot for a personal portfolio website. You impersonate the website's owner.
          Answer the user's questions based on the below context.
          Whenever it makes sense, provide links to pages that contain more information about the topic from the given context.
          Format your messages as a script which would be used by an assistant as it is .\n\n"
          Context: {context}
         """),
         MessagesPlaceholder('chat_history'),
         HumanMessagePromptTemplate.from_template("{input}")
    ])

    chat_history = messsage_history.get(session_id,[])

    combine_docs_chain = create_stuff_documents_chain(
            llm=llm,
            prompt=prompt,
            document_prompt=PromptTemplate.from_template(
            "Page URL: {source}\n\nPage content:\n{page_content}",
            ),
            document_separator= "\n--------\n",
        )

    retrieval_chain = create_retrieval_chain(
        combine_docs_chain=combine_docs_chain,
        retriever=retriever
        )
    
    response = retrieval_chain.invoke({
        "input":question,
        "chat_history":chat_history
    })

    # print(response)
    # pprint.pp(response)
    return response['answer']

def transcribe(audio_content):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_file.write(audio_content.read())
        temp_file_name = temp_file.name

    with open(temp_file_name, "rb") as audio_file:
        transcription = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )

    os.remove(temp_file_name)
    return transcription.text