import argparse
import json
import uvicorn
from bot_sts import run_bot
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse
from twilio.rest import Client
from fastapi import Response
import os
from dotenv import load_dotenv

load_dotenv(override = True)

app = FastAPI()

@app.post("/start_call/")
async def start_call():
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
    client = Client(account_sid, auth_token)
    twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER")
    target_phone_number = os.getenv("TARGET_PHONE_NUMBER")
    base_url = os.getenv("BASE_URL")
    try:
        call = client.calls.create(
            to = target_phone_number,
            from_= twilio_phone_number,
            url=f"{base_url}/twiml_outbound",
            time_limit = 90
        )
        return {"call_sid": call.sid, "status": call.status}
    except Exception as e:
        print(status_code = 500, detail = str(e))

@app.post("/twiml_outbound")
async def twiml_outbound():
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Connect>
                <Stream url="{websocket_base_url()}/ws"></Stream>
            </Connect>
            <Pause length="40"/>
        </Response>
    """
    return Response(content = twiml, media_type = "application/xml")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    start_data = websocket.iter_text()
    await start_data.__anext__()
    call_data = json.loads(await start_data.__anext__())
    print(call_data, flush = True)
    stream_sid = call_data["start"]["streamSid"]
    print("WebSocket connection accepted")
    await run_bot(websocket, stream_sid)

def websocket_base_url():
    base_url = os.getenv("BASE_URL")
    return base_url.replace("http://", "ws://").replace("https://", "wss://")

if __name__ == "__main__":
    uvicorn.run(app, host = "0.0.0.0", port = 8080)
