import datetime
import io
import os
import sys
import wave
import aiofiles
from fastapi import WebSocket
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.cartesia.stt import CartesiaSTTService
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

logger.remove(0)
logger.add(sys.stderr, level = "DEBUG")


async def save_audio(server_name: str, audio: bytes, sample_rate: int, num_channels: int):
    if len(audio) > 0:
        filename = (
            f"{server_name}_recording_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        )
        with io.BytesIO() as buffer:
            with wave.open(buffer, "wb") as wf:
                wf.setsampwidth(2)
                wf.setnchannels(num_channels)
                wf.setframerate(sample_rate)
                wf.writeframes(audio)
            async with aiofiles.open(filename, "wb") as file:
                await file.write(buffer.getvalue())
        logger.info(f"Merged audio saved to {filename}")
    else:
        logger.info("No audio data to save")


async def run_bot(websocket_client: WebSocket, stream_sid: str):
    transport = FastAPIWebsocketTransport(
        websocket = websocket_client,
        params=FastAPIWebsocketParams(
            audio_in_enabled = True,
            audio_out_enabled = True,
            add_wav_header = False,
            vad_enabled = True,
            vad_analyzer = SileroVADAnalyzer(),
            vad_audio_passthrough = True,
            serializer=TwilioFrameSerializer(stream_sid),
        ),
    )

    llm = GoogleLLMService(
        api_key = os.getenv("GOOGLE_API_KEY"),
        model = "gemini-2.0-flash",
        system_instruction =
            """
            Eres un comico que cuenta chistes cortos de humor blanco,
            no expliques el chiste si no te lo piden, 
            no cuentes otro si no te lo piden. 
            """,
        params = GoogleLLMService.InputParams(
            temperature = 0.7,
            max_tokens = 2000
        )
    )

    stt = CartesiaSTTService(
        api_key = os.getenv("CARTESIA_API_KEY"),
        model = "ink-whisper",
        language = "es"
    )

    tts = CartesiaTTSService(
        api_key = os.getenv("CARTESIA_API_KEY"),
        voice_id = "5c5ad5e7-1020-476b-8b91-fdcbe9cc313c",
        model = "sonic-2",
        params = CartesiaTTSService.InputParams(
            language = "es",
            speed = "normal"
        )
    )

    messages = [
        {
            "role": "system",
            "content": """
                Eres un comico que cuenta chistes cortos de humor blanco,
                no expliques el chiste si no te lo piden, 
                no cuentes otro si no te lo piden.             
            """,
        },
    ]

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    # NOTE: Watch out! This will save all the conversation in memory. You can
    # pass `buffer_size` to get periodic callbacks.
    audiobuffer = AudioBufferProcessor()

    pipeline = Pipeline(
        [
            transport.input(),  # Websocket input from client
            stt,  # Speech-To-Text
            context_aggregator.user(),
            llm,  # LLM
            tts,  # Text-To-Speech
            transport.output(),  # Websocket output to client
            audiobuffer,  # Used to buffer the audio in the pipeline
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params = PipelineParams(
            audio_in_sample_rate = 8000,
            audio_out_sample_rate = 8000,
            allow_interruptions = True,
        ),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        # Start recording.
        await audiobuffer.start_recording()
        # Kick off the conversation.
        messages.append({"role": "system", "content": "Presentate al usuario"})
        await task.queue_frames([context_aggregator.user().get_context_frame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await task.cancel()

    @audiobuffer.event_handler("on_audio_data")
    async def on_audio_data(buffer, audio, sample_rate, num_channels):
        server_name = f"server_{websocket_client.client.port}"
        await save_audio(server_name, audio, sample_rate, num_channels)

    # We use `handle_sigint=False` because `uvicorn` is controlling keyboard
    # interruptions. We use `force_gc=True` to force garbage collection after
    # the runner finishes running a task which could be useful for long running
    # applications with multiple clients connecting.
    runner = PipelineRunner(handle_sigint = False, force_gc = True)

    await runner.run(task)