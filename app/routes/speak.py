from fastapi import APIRouter, UploadFile,File, WebSocket,Request
from app import llm, vectorStore, embeddings
from langchain.prompts import PromptTemplate
from fastapi.responses import JSONResponse,StreamingResponse,HTMLResponse
from ..controller.chain import getAnswerUsingVectorResult,getAudioForTheText,transcribe
from ..controller.realtime import handle_media_stream
from twilio.twiml.voice_response import VoiceResponse, Connect, Say, Stream
import io

router = APIRouter()

@router.get("/")
async def read_root():
    return {"message": f"Hello from FastAPI"}

@router.get('/ask')
async def ask(question:str):
    print(question)
    template = PromptTemplate.from_template(""" Answer the question asked by the user funningly.
                                            Question: {question}
                                            """)
    chain = template | llm
    response = chain.invoke({
        "question":question
    })
    print(response)
    data = {
        "question":question,
        "answer":response.content
    }
    return JSONResponse(content=data,status_code=200)


@router.get('/answers')
def getAnswer(question:str,session_id:str):
    # Creating question embedding
    text_response = getAnswerUsingVectorResult(session_id,question)
    print("Got text response")
    audio_stream_response = getAudioForTheText(text_response)
    # return JSONResponse(content={"message":textResponse},status_code=200)
    print("Got audio response")
    # return Response(audioResponse, media_type="audio/mpeg")
    return StreamingResponse(audio_stream_response,media_type="audio/wav")

@router.post("/transcribe")
async def upload_audio(audio: UploadFile = File(...)):
    # audio.filename, audio.content_type available
    # audio_blob = await audio.read() 
     # bytes of the audio file
    audio_bytes = await audio.read()
    file_like = io.BytesIO(audio_bytes)
    response = transcribe(audio_content=file_like)

    return JSONResponse(content={"response":response},status_code=200)


@router.post("/talk")
async def upload_audio(session_id:str,audio: UploadFile = File(...)):
    # audio.filename, audio.content_type available
    # audio_blob = await audio.read() 
     # bytes of the audio file
    audio_bytes = await audio.read()
    file_like = io.BytesIO(audio_bytes)
    question = transcribe(audio_content=file_like)
    text_response = getAnswerUsingVectorResult(session_id,question)
    print("Got text response")
    audio_stream_response = getAudioForTheText(text_response)
    # return JSONResponse(content={"message":textResponse},status_code=200)
    print("Got audio response")
    # return Response(audioResponse, media_type="audio/mpeg")
    return StreamingResponse(audio_stream_response,media_type="audio/wav")

@router.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    response = VoiceResponse()
    # <Say> punctuation to improve text-to-speech flow
    response.say("Please wait while we connect your call")
    response.pause(length=1)
    response.say("O.K. you can start talking!")
    host = request.url.hostname
    connect = Connect()
    connect.stream(url=f'wss://{host}/media-stream')
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")

@router.websocket("/media-stream")
async def handle_twillio(websocket: WebSocket):
    await handle_media_stream(websocket)
    
    


