import os
import json
import base64
import asyncio
import websockets
from fastapi import WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
from openai import OpenAI  # Official OpenAI Python SDK for vector store
from .chain import transcribe,getAnswerUsingVectorResult
import io
from app import vectorStore

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

SYSTEM_MESSAGE = (
    "You are a helpful AI assistant who answers questionsfor the owner of the portfolio website. "
    "The owner of the website is Bibhash Singh"
    "Use the provided context from the knowledge base "
    "to answer the user's questions accurately."
)

VOICE = 'alloy'  # AI voice for audio responses

function_call_output_id = "1"

# Store conversation context per session
sessions_context = {}


async def send_session_update(openai_ws, context_text):
    """Send session update with instructions and context to OpenAI Realtime API."""
    # instructions = SYSTEM_MESSAGE + "\n\nContext:\n" + context_text
    instructions = SYSTEM_MESSAGE
    session_update = {
        "type": "session.update",
        "session": {
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": VOICE,
            "instructions": instructions,
            "modalities": ["text", "audio"],
            "temperature": 0.8,
            "input_audio_transcription": {
                 "model": "whisper-1"
            },
            "tools": [ 
                        {
                            "type": "function",
                            "name": "question_and_answer",
                            "description": "Get answers to any questions asked about Bibhash Singh",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "question": { "type": "string" }
                                },
                                "required": ["question"]
                            }
                        }
                    ],
                    "tool_choice": "auto"  
        }
    }
    await openai_ws.send(json.dumps(session_update))

async def handle_media_stream(websocket: WebSocket):
    try:
        queuedFirstMessage = None
    
        await websocket.accept()
        session_id = id(websocket)  # Simple session identifier
        sessions_context[session_id] = ""  # Initialize empty context
        
        async with websockets.connect(
            'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
            extra_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as openai_ws:

            # Initially send session update with empty context
            await send_session_update(openai_ws, sessions_context[session_id])
            
            if queuedFirstMessage is not None:
                await openai_ws.send(json.dumps(queuedFirstMessage))
                await openai_ws.send(json.dumps({"type":"response.create"}))
                queuedFirstMessage = None
            
            stream_sid = None

            async def receive_from_twilio():
                nonlocal stream_sid
                nonlocal queuedFirstMessage
                audio_chunks = []
                try:
                    async for message in websocket.iter_text():
                        data = json.loads(message)
                        if data['event'] == 'media' and openai_ws.open:
                            # Forward raw audio to OpenAI realtime API
                            audio_append = {
                                "type": "input_audio_buffer.append",
                                "audio": data['media']['payload']
                            }
                            b64_audio = data["media"]["payload"]
                            raw_audio = base64.b64decode(b64_audio)
                            audio_chunks.append(raw_audio)
                            await openai_ws.send(json.dumps(audio_append))

                        elif data['event'] == 'start':
                            stream_sid = data['start']['streamSid']
                            queuedFirstMessage = {
                                "type": 'conversation.item.create',
                                "item": {
                                    "type": 'message',
                                    "role": 'user',
                                    "content": [{ "type": 'input_text', 
                                                 "text": "How can i assist you today?" 
                                                }],
                                
                                }
                            }
                            if queuedFirstMessage is not None:
                                # Send first message
                                await openai_ws.send(json.dumps(queuedFirstMessage))
                                await openai_ws.send(json.dumps({"type":"response.create"}))
                                queuedFirstMessage = None



                        elif data['event'] == 'stop':
                            # When user stops speaking, we want to get the transcribed text
                            # For this example, assume OpenAI realtime API sends a text transcript event
                            pass

                        # elif data['event'] == 'speech_started':
                        #     print("Speech started")
                        #     audio_chunks = []

                        # elif data['event'] == 'speech_stopped':
                        #     print("Speech stopped")
                        #     full_audio = b"".join(audio_chunks)
                        #     file_like = io.BytesIO(full_audio)
                        #     text = transcribe(file_like)
                        #     print("Transcruied text: " )
                        #     print(text)
                        #     context_text = "My name is Bibhash Singh"
                        #     sessions_context[session_id] = context_text
                        #     await send_session_update(openai_ws, context_text)


                except WebSocketDisconnect as e:
                    print(e)
                    if openai_ws.open:
                        await openai_ws.close()

            async def send_to_twilio():
                nonlocal stream_sid
                try:
                    async for openai_message in openai_ws:
                        response = json.loads(openai_message)
                        # print(response.get('type'))
                        if response.get('type') == 'error':
                            print("Error")
                            print(response)

                        if response.get('type') == 'conversation.item.input_audio_transcription.completed':
                            user_text = response.get('transcript','').strip()

                        if response.get('type') == 'input_audio_buffer.speech_started':
                            # await websocket.send_json({
                            #     "streamSid":stream_sid
                            # })
                            await openai_ws.send(json.dumps({
                                "type":"response.cancel"
                            }))

                        if response.get('type') == 'response.function_call_arguments.done':
                            function_name = response.get('name')
                            arguments = json.loads(response.get('arguments'))
                            print("Arguments : "  , arguments)
                            if function_name == 'question_and_answer':
                                print("****************************")
                                print("QUESTION and ANSWER Tool called")
                                print(response)
                                print("*****************************")
                                question = arguments['question']
                                print("Question asked :  " , question)
                                answer = getAnswerUsingVectorResult(stream_sid,question)
                                print("Answer : " , answer)
                                functionOutputEvent = {
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "function_call_output",
                                        # "role": "system",
                                        "output": answer,
                                        "call_id":function_call_output_id
                                    }
                                }
                                await openai_ws.send(json.dumps(functionOutputEvent))
                                await openai_ws.send(json.dumps({
                                    "type":"response.create",
                                    "response":{
                                        "modalities":["text","audio"],
                                        "instructions":f"Respond to the user's question {question} based on this information: {answer}. Be concise and friendly."
                                    }
                                }))


                        # Log events for debugging
                        if response.get('type') == 'response.audio.delta' and response.get('delta'):
                            # Re-encode audio delta for Twilio
                            audio_payload = base64.b64encode(base64.b64decode(response['delta'])).decode('utf-8')
                            audio_delta = {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": audio_payload
                                }
                            }
                            await websocket.send_json(audio_delta)

                except Exception as e:
                    print("Error received")
                    print(e)
                    await openai_ws.send(json.dumps({
                        "type":"response.create",
                        "response":{
                            "modalities":["text","audio"],
                            "instructions":"I apologize, but I'm having trouble processing your request right now. Is there anything else I can help you with?" 
                        }
                    }))


            await asyncio.gather(receive_from_twilio(), send_to_twilio())
    except Exception as e:
        print("Got exception in main ")
        print(e)
