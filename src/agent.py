import asyncio
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    ChatContext,
    ChatMessage,
    JobContext,
    JobProcess,
    cli,
    get_job_context,
    inference,
    room_io,
)
from livekit.agents.llm import ImageContent
from livekit.plugins import bey, noise_cancellation, silero

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# TTS voice configuration
# Voice can be configured via environment variable in .env.local
# If not set, default value will be used
# Voice is verified Cartesia Sonic-3 voice from the official library
VOICE_ID = os.getenv(
    "VOICE_MODERATOR", "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
)

# Avatar configuration
# Avatar is from Beyond Presence
AVATAR_ID = os.getenv(
    "AVATAR_MODERATOR", "7c9ca52f-d4f7-46e1-a4b8-0c8655857cc3"
)

# Beyond Presence API key
# Uses BEY_API_KEY-3 from environment variables
BEY_API_KEY = os.getenv("BEY_API_KEY-3") or os.getenv("BEY_API_KEY3") or os.getenv("BEY_API_KEY")


class BaseAgent(Agent):
    """Base agent class with common vision capabilities for screen sharing and multi-agent chat."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._latest_frame: Optal[rtc.VideoFrame] = None
        self._video_stream: Optal[rtc.VideoStream] = None
        self._tasks = []  # Prevent garbage collection of running tasks

    async def on_enter(self) -> None:
        """Set up video stream monitoring when agent enters."""
        await self._setup_video_stream()

    async def _setup_video_stream(self) -> None:
        """Set up video stream to capture frames from user's camera or screen share."""
        try:
            room = get_job_context().room
            logger.info("Setting up video stream for screen sharing vision...")

            # Find the first video track from remote participants
            for participant in room.remote_participants.values():
                # Skip avatar participant
                if participant.identity == "bey-avatar-agent":
                    continue
                    
                for publication in participant.track_publications.values():
                    if (
                        publication.track
                        and publication.track.kind == rtc.TrackKind.KIND_VIDEO
                    ):
                        logger.info(f"Found video track from participant {participant.identity}, setting up stream...")
                        self._create_video_stream(publication.track)
                        return

            # Watch for new video tracks
            @room.on("track_subscribed")
            def on_track_subscribed(
                track: rtc.Track,
                publication: rtc.RemoteTrackPublication,
                participant: rtc.RemoteParticipant,
            ):
                # Skip avatar participant
                if participant.identity == "bey-avatar-agent":
                    return
                    
                if track.kind == rtc.TrackKind.KIND_VIDEO:
                    logger.info(f"New video track subscribed from {participant.identity}, setting up stream...")
                    self._create_video_stream(track)

            logger.info("Video stream monitoring set up. Waiting for video tracks...")
        except Exception as e:
            logger.warning(f"Could not set up video stream: {e}")

    def _create_video_stream(self, track: rtc.Track) -> None:
        """Create a video stream to buffer the latest frame from the user's track."""
        # Close any existing stream (we only want one at a time)
        if self._video_stream is not None:
            self._video_stream.close()

        # Create a new stream to receive frames
        self._video_stream = rtc.VideoStream(track)

        async def read_stream():
            try:
                async for event in self._video_stream:
                    # Store the latest frame for use later
                    self._latest_frame = event.frame
            except Exception as e:
                logger.debug(f"Video stream ended: {e}")

        # Store the async task
        task = asyncio.create_task(read_stream())
        task.add_done_callback(lambda t: self._tasks.remove(t) if t in self._tasks else None)
        self._tasks.append(task)

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        """Add the latest video frame to the user's message if available."""
        if self._latest_frame:
            try:
                new_message.content.append(ImageContent(image=self._latest_frame))
                logger.info("Added video frame to user message - avatar can now see the screen share")
                self._latest_frame = None
            except Exception as e:
                logger.warning(f"Could not add video frame to message: {e}")
        else:
            logger.debug("No video frame available to add to message")



class ModeratorAgent(BaseAgent):
    """Moderator Agent - The main AI assistant for OnePlan."""

    def __init__(self, chat_ctx: Optional[ChatContext] = None) -> None:
        super().__init__(
            instructions="""You are the official AI Moderator for OnePlan. Your primary mission is to keep the room productive, professional, and focused on financial planning, insurance, investments, retirement strategies, tax optimization, and everything related to OnePlan products and services.

CRITICAL COMMUNICATION RULES:
- Be concise and direct. Say only what's necessary. Avoid filler words, unnecessary explanations, or lengthy introductions.
- Keep responses brief but complete. Get to the point quickly.

VISION CAPABILITY:
- You have vision capabilities and can see the user's screen if they share it.
- When a video frame is included in the user's message, analyze what you see carefully.
- Provide relevant insights, feedback, or assistance based on the visual content you observe.
- If you see financial data, spreadsheets, reports, or documents, analyze them and provide helpful commentary.
- If you see the user's screen but it's unclear, ask clarifying questions about what they want help with.

Key rules:
- Professional, clear, helpful. No emojis, slang, or informal tone.
- If unsure about regulations or product details, direct to official documentation.
- Maintain neutrality in discussions about team changes or leadership.
- All conversations in English.

Tone: Professional, calm, authoritative when needed.""",
            chat_ctx=chat_ctx,
            tts=inference.TTS(
                model="cartesia/sonic-3", voice=VOICE_ID
            ),
        )

    async def on_enter(self) -> None:
        await super().on_enter()  # Set up video stream
        logger.info(f"ModeratorAgent entered with voice {VOICE_ID}")
        await self.session.generate_reply(
            instructions="Greet the user briefly and professionally. Keep it short. Mention you can help with OnePlan services. You can see their screen if shared."
        )




server = AgentServer()


def prewarm(proc: JobProcess):
    """Preload VAD model for better performance."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def my_agent(ctx: JobContext):
    """Main agent entry point with vision support for screen sharing."""
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline with vision capabilities
    # Using GPT-4.1-mini with vision support for screen sharing analysis
    session = AgentSession(
        # Speech-to-text (STT) - converts user's speech to text
        stt=inference.STT(model="assemblyai/universal-streaming", language="en"),
        # Large Language Model (LLM) with vision capabilities
        # GPT-4.1-mini supports vision and can analyze screen shares
        llm=inference.LLM(model="openai/gpt-4.1-mini"),
        # Text-to-speech (TTS)
        tts=inference.TTS(
            model="cartesia/sonic-3", voice=VOICE_ID
        ),
        # VAD and turn detection for natural conversation flow
        vad=ctx.proc.userdata["vad"],
        # Preemptive generation reduces latency
        preemptive_generation=True,
    )

    # Initialize avatar BEFORE starting the session (as per Beyond Presence docs)
    if BEY_API_KEY and AVATAR_ID:
        try:
            avatar = bey.AvatarSession(
                avatar_id=AVATAR_ID,
                api_key=BEY_API_KEY,
                avatar_participant_identity="bey-avatar-agent",
                avatar_participant_name="bey-avatar-agent",
            )
            await avatar.start(session, room=ctx.room)
            session._current_avatar = avatar
            logger.info("Avatar initialized successfully")
        except Exception as e:
            logger.warning(f"Could not initialize avatar: {e}")
    else:
        logger.warning("No BEY_API_KEY or AVATAR_ID found, running without avatar")

    # Start the session with video input enabled for screen sharing
    moderator_agent = ModeratorAgent()
        # Join the room and connect to the user
    await ctx.connect()
    await session.start(
        agent=moderator_agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            # Enable video input so agent can see screen shares
            video_input=True,
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony()
                if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                else noise_cancellation.BVC(),
            ),
        ),
    )




if __name__ == "__main__":
    cli.run_app(server)

