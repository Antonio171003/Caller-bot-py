# Caller‑Bot‑Py

Real-time phone calls using Twilio, Pipecat, Cartesia, and Gemini AI for audio processing and conversational logic.
Records and saves each call as an audio file.

## Repository Structure

- **`bot.py`**  
  Audio pipeline with Pipecat:  
  `Twilio MediaStream → STT (Cartesia Ink‑Whisper) → LLM (Gemini AI) → TTS (Cartesia Sonic‑2) → output back to Twilio`

- **`bot_sts.py`**  
  A stateful bot using only Gemini AI for STS logic (no speech components).

- **`server.py`**  
  A Flask or FastAPI server:
  - `POST /start_call`: returns TwiML with `<Stream>` for audio routing  
  - `WebSocket /ws`: handles Twilio MediaStreams via Pipecat

- `.env.example` — environment variable template  
- `requirements.txt` — Python dependencies

---

## Technologies Used

- **Pipecat**: modular conversational pipelines in Python  
- **Twilio Media Streams**: real-time WebSocket audio with Pipecat  
- **Cartesia**:  
  - **STT Ink‑Whisper** (~100 ms latency)  
  - **TTS Sonic‑2** (~90 ms latency)
- **Gemini AI**: LLM

---

## Setup & Installation

```bash
git clone https://github.com/Antonio171003/Caller-bot-py.git
cd Caller-bot-py
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy environment variables:

```bash
cp .env.example .env
```

Then configure:

```env
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
CARTESIA_API_KEY=
GEMINI_API_KEY=
WEBHOOK_URL=   # Public URL (e.g. via ngrok)
```

## Running

Start the server:

```bash
python3 server.py
```

Trigger a call with curl:

```
curl -X POST https://<your-ngrok-domain>/start_call/
```


