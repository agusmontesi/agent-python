import asyncio
import json
import logging
import os
import time
from typing import Optional, Tuple, Dict, Any

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
    RunContext,
    cli,
    function_tool,
    get_job_context,
    inference,
    room_io,
)
from livekit.agents.llm import ImageContent
from livekit.plugins import bey, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# TTS voice configuration for each agent
# Voices can be configured via environment variables in .env.local
# If not set, default values will be used
# All voices are verified Cartesia Sonic-3 voices from the official library
# Each agent has a unique voice to ensure distinct identification
VOICE_IDS = {
    # Moderator: Jacqueline - Confident, young American adult female
    "moderator": os.getenv(
        "VOICE_MODERATOR", "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
    ),
    # CFO: Blake - Energetic American adult male (executive tone)
    "cfo": os.getenv(
        "VOICE_CFO", "a167e0f3-df7e-4d52-a9c3-f949145efdab"
    ),
    # Finance Director: Robyn - Neutral, mature Australian female (analytical tone)
    "finance_director": os.getenv(
        "VOICE_FINANCE_DIRECTOR", "694f9389-aac1-45b6-b726-9d9369183238"
    ),
    # Sales Director: Blake variant or energetic voice (using verified voice)
    "sales_director": os.getenv(
        "VOICE_SALES_DIRECTOR", "e07c00bc-4134-4eae-9ea4-1a55fb45746b"
    ),
}

# Avatar configuration for each agent
# Avatares are from Beyond Presence
# Each agent has a unique avatar to ensure distinct visual identification
AVATAR_IDS = {
    # Moderator: First avatar
    "moderator": os.getenv(
        "AVATAR_MODERATOR", "7c9ca52f-d4f7-46e1-a4b8-0c8655857cc3"
    ),
    # CFO: Second avatar
    "cfo": os.getenv(
        "AVATAR_CFO", "7124071d-480e-4fdc-ad0e-a2e0680f1378"
    ),
    # Finance Director: First avatar (same as moderator)
    "finance_director": os.getenv(
        "AVATAR_FINANCE_DIRECTOR", "7c9ca52f-d4f7-46e1-a4b8-0c8655857cc3"
    ),
    # Sales Director: Second avatar (same as CFO)
    "sales_director": os.getenv(
        "AVATAR_SALES_DIRECTOR", "7124071d-480e-4fdc-ad0e-a2e0680f1378"
    ),
}

# Beyond Presence API keys for each agent
# Allows using different API keys for different avatares if needed
BEY_API_KEYS = {
    "moderator": os.getenv("BEY_API_KEY"),
    "cfo": os.getenv("BEY_API_KEY2"),
    "finance_director": os.getenv("BEY_API_KEY"),
    "sales_director": os.getenv("BEY_API_KEY2"),
}


def decode_token_and_extract_meeting_config(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodifica el token JWT y extrae meetingConfig del metadata.
    """
    try:
        import jwt
        
        # Decodificar el token sin verificar la firma
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        # Log completo del token decodificado
        logger.info("=" * 80)
        logger.info("TOKEN JWT DECODIFICADO - CONTENIDO COMPLETO:")
        logger.info("=" * 80)
        logger.info(json.dumps(decoded, indent=2, ensure_ascii=False))
        logger.info("=" * 80)
        
        # El meetingConfig está en el campo 'metadata' como string JSON
        metadata_str = decoded.get('metadata')
        if metadata_str:
            logger.info(f"Metadata encontrado en token (tipo: {type(metadata_str)}): {metadata_str}")
            
            # Parsear el metadata como JSON
            if isinstance(metadata_str, str):
                try:
                    metadata_dict = json.loads(metadata_str)
                    logger.info(f"Metadata parseado: {json.dumps(metadata_dict, indent=2, ensure_ascii=False)}")
                    
                    # Extraer meeting_config del metadata
                    meeting_config = metadata_dict.get('meeting_config')
                    if meeting_config:
                        logger.info("=" * 80)
                        logger.info("MEETING CONFIG EXTRAÍDO DEL TOKEN:")
                        logger.info("=" * 80)
                        logger.info(json.dumps(meeting_config, indent=2, ensure_ascii=False))
                        logger.info("=" * 80)
                        return meeting_config
                    else:
                        logger.warning("No se encontró 'meeting_config' en metadata")
                except json.JSONDecodeError as e:
                    logger.error(f"Error parseando metadata como JSON: {e}")
            else:
                logger.warning(f"Metadata no es un string, es: {type(metadata_str)}")
        else:
            logger.warning("No se encontró 'metadata' en el token")
            
    except Exception as e:
        logger.error(f"Error decodificando token: {e}", exc_info=True)
    
    return None


def extract_meeting_config_from_participant(participant: rtc.RemoteParticipant) -> Optional[Dict[str, Any]]:
    """
    Extrae meetingConfig del participante.
    Intenta obtenerlo de metadata primero, luego del token JWT si está disponible.
    """
    meeting_config = None
    
    # Log información del participante
    logger.info("=" * 80)
    logger.info("INFORMACIÓN DEL PARTICIPANTE:")
    logger.info("=" * 80)
    logger.info(f"Identity: {participant.identity}")
    logger.info(f"Name: {participant.name}")
    logger.info(f"SID: {participant.sid}")
    logger.info(f"Kind: {participant.kind}")
    logger.info(f"Metadata (raw): {participant.metadata}")
    logger.info(f"Metadata (type): {type(participant.metadata)}")
    logger.info("=" * 80)
    
    # Método 1: Intentar desde metadata del participante
    # LiveKit puede exponer el metadata del token en el participante
    if hasattr(participant, 'metadata') and participant.metadata:
        try:
            logger.info(f"Procesando metadata del participante (tipo: {type(participant.metadata)})...")
            
            # Si metadata es un string JSON, parsearlo
            if isinstance(participant.metadata, str):
                # Intentar parsear como JSON
                try:
                    metadata_dict = json.loads(participant.metadata)
                except json.JSONDecodeError:
                    # Si no es JSON válido, puede ser que el metadata del token esté aquí
                    # El metadata del token puede contener otro JSON string dentro
                    logger.info(f"Metadata no es JSON válido directamente, intentando otras formas...")
                    metadata_dict = {"raw": participant.metadata}
            else:
                metadata_dict = participant.metadata
            
            logger.info(f"Metadata parseado del participante: {json.dumps(metadata_dict, indent=2, ensure_ascii=False, default=str)}")
            
            # Buscar meetingConfig en metadata (puede estar en diferentes lugares)
            if isinstance(metadata_dict, dict):
                # Intentar diferentes nombres de campos
                meeting_config = (
                    metadata_dict.get('meetingConfig') or 
                    metadata_dict.get('meeting_config') or
                    metadata_dict.get('meetingConfig')  # También puede estar anidado
                )
                
                # Si no está directamente, buscar en un nivel más profundo
                if not meeting_config:
                    # El metadata del token puede tener la estructura: {"meeting_config": {...}}
                    for key in ['meeting_config', 'meetingConfig', 'metadata']:
                        if key in metadata_dict:
                            value = metadata_dict[key]
                            if isinstance(value, str):
                                try:
                                    nested = json.loads(value)
                                    if isinstance(nested, dict):
                                        meeting_config = nested.get('meeting_config') or nested.get('meetingConfig')
                                        if meeting_config:
                                            break
                                except:
                                    pass
                            elif isinstance(value, dict):
                                meeting_config = value.get('meeting_config') or value.get('meetingConfig')
                                if meeting_config:
                                    break
                
                if meeting_config:
                    logger.info("=" * 80)
                    logger.info("MEETING CONFIG OBTENIDO DE METADATA DEL PARTICIPANTE:")
                    logger.info("=" * 80)
                    logger.info(json.dumps(meeting_config, indent=2, ensure_ascii=False, default=str))
                    logger.info("=" * 80)
                    return meeting_config
                else:
                    logger.warning("No se encontró meeting_config en metadata del participante")
        except (json.JSONDecodeError, AttributeError, Exception) as e:
            logger.error(f"Error procesando metadata del participante: {e}", exc_info=True)
    
    # Método 2: El token no está disponible directamente en participant.identity
    # El token se debe obtener del JobContext o de otra fuente
    # Por ahora, retornamos None y lo manejaremos en my_agent
    
    return None


class BaseAgent(Agent):
    """Base agent class with common vision capabilities for screen sharing and multi-agent chat."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._latest_frame: Optional[rtc.VideoFrame] = None
        self._video_stream: Optional[rtc.VideoStream] = None
        self._tasks = []  # Prevent garbage collection of running tasks
        self._just_entered = True  # Flag to prevent immediate transfers
        self._enter_time = None
        self._meeting_config: Optional[Dict[str, Any]] = None  # Almacenar meeting config

    def get_meeting_config(self) -> Optional[Dict[str, Any]]:
        """Obtener el meeting config actual."""
        return self._meeting_config

    def set_meeting_config(self, config: Optional[Dict[str, Any]]) -> None:
        """Establecer el meeting config."""
        self._meeting_config = config
        if config:
            logger.info(f"Meeting config establecido: title={config.get('title')}, questions={config.get('importantQuestions')}, topics={config.get('topics')}")

    async def on_enter(self) -> None:
        """Set up video stream monitoring when agent enters."""
        await self._setup_video_stream()
        self._enter_time = time.time()
        self._just_entered = True

    async def _setup_video_stream(self) -> None:
        """Set up video stream to capture frames from user's camera or screen share."""
        try:
            room = get_job_context().room

            # Find the first video track from remote participants
            for participant in room.remote_participants.values():
                for publication in participant.track_publications.values():
                    if (
                        publication.track
                        and publication.track.kind == rtc.TrackKind.KIND_VIDEO
                    ):
                        self._create_video_stream(publication.track)
                        return

            # Watch for new video tracks
            @room.on("track_subscribed")
            def on_track_subscribed(
                track: rtc.Track,
                publication: rtc.RemoteTrackPublication,
                participant: rtc.RemoteParticipant,
            ):
                if track.kind == rtc.TrackKind.KIND_VIDEO:
                    self._create_video_stream(track)

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
                self._latest_frame = None
            except Exception as e:
                logger.debug(f"Could not add video frame to message: {e}")

    def _check_transfer_allowed(self) -> Tuple[bool, str]:
        """Check if transfer is allowed based on time since entry."""
        if self._just_entered and self._enter_time:
            elapsed = time.time() - self._enter_time
            if elapsed < 30:
                logger.info(f"Preventing transfer - only {elapsed:.1f}s since entry")
                return False, f"Please wait for the user to respond first. Only {elapsed:.1f} seconds have passed since entry."
        self._just_entered = False
        return True, ""

    async def _change_avatar(self, agent_key: str) -> None:
        """Change the avatar to match the current agent."""
        try:
            room = get_job_context().room
            session = self.session

            # Get current avatar from session userdata if it exists
            current_avatar = getattr(session, "_current_avatar", None)

            # Close current avatar if it exists
            if current_avatar is not None:
                try:
                    await current_avatar.aclose()
                    logger.info("Current avatar stopped successfully")
                    # Small delay to ensure complete closure
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Error stopping current avatar: {e}")

            # Get avatar ID and API key for this agent
            avatar_id = AVATAR_IDS.get(agent_key)
            api_key = BEY_API_KEYS.get(agent_key)

            if not avatar_id:
                logger.warning(f"No avatar ID configured for {agent_key}")
                return

            if not api_key:
                logger.warning(f"No API key configured for {agent_key}, using BEY_API_KEY")
                api_key = os.getenv("BEY_API_KEY")

            if not api_key:
                logger.error("No BEY_API_KEY found in environment")
                return

            # Create new avatar session
            new_avatar = bey.AvatarSession(
                avatar_id=avatar_id,
                api_key=api_key,
                avatar_participant_identity="bey-avatar-agent",  # Same for all to reuse participant slot
                avatar_participant_name="bey-avatar-agent",
            )

            # Start the new avatar
            await new_avatar.start(session, room=room)

            # Store reference in session
            session._current_avatar = new_avatar

            logger.info(f"Avatar successfully changed to {agent_key}")
        except Exception as e:
            logger.error(f"Error changing avatar to {agent_key}: {e}")


class ModeratorAgent(BaseAgent):
    """Moderator Agent - The main coordinator that can transfer to other specialists."""

    def __init__(self, chat_ctx: Optional[ChatContext] = None) -> None:
        super().__init__(
            instructions="""You are the official AI Moderator for OnePlan. Your primary mission is to keep the room productive, professional, and focused on financial planning, insurance, investments, retirement strategies, tax optimization, and everything related to OnePlan products and services.

CRITICAL COMMUNICATION RULES:
- Be concise and direct. Say only what's necessary. Avoid filler words, unnecessary explanations, or lengthy introductions.
- Keep responses brief but complete. Get to the point quickly.
- You can see the user's screen if they share it. Analyze what you see and provide relevant insights based on the visual content.
- Transfer specialized inquiries to: CFO (strategic financial topics), Finance Director (detailed financial analysis), Sales Director (sales strategies).
- Maintain full conversation context when transferring to other agents.

Key rules:
- Professional, clear, helpful. No emojis, slang, or informal tone.
- If unsure about regulations or product details, direct to official documentation.
- Maintain neutrality in discussions about team changes or leadership.
- All conversations in English.

Tone: Professional, calm, authoritative when needed.""",
            chat_ctx=chat_ctx,
            tts=inference.TTS(
                model="cartesia/sonic-3", voice=VOICE_IDS["moderator"]
            ),
        )

    async def on_enter(self) -> None:
        await super().on_enter()  # Set up video stream
        logger.info(f"ModeratorAgent entered with voice {VOICE_IDS['moderator']}")
        # Change avatar to moderator
        await self._change_avatar("moderator")
        await self.session.generate_reply(
            instructions="Greet the user briefly and professionally. Keep it short. Mention you can help with OnePlan services and transfer to specialists if needed. You can see their screen if shared."
        )

    @function_tool()
    async def transfer_to_cfo(self, context: RunContext) -> tuple:
        """Transfer to the CFO for high-level financial strategy, executive decisions, and strategic investment analysis. Use when user asks about strategic financial planning, corporate finance, or executive-level financial decisions."""
        try:
            await self.session.say("Transferring you to our CFO.")
            logger.info("Transferring to CFOAgent")
            return CFOAgent(chat_ctx=self.chat_ctx), "Transferring to CFO"
        except Exception as e:
            logger.error(f"Error transferring to CFO: {e}")
            await self.session.say("I apologize, but I encountered an issue with the transfer. Please try again.")
            return None, "Transfer failed"

    @function_tool()
    async def transfer_to_finance_director(self, context: RunContext) -> tuple:
        """Transfer to the Finance Director for detailed financial analysis, financial reports, and operational financial management. Use when user asks about detailed financial analysis, reports, or operational finance."""
        try:
            await self.session.say("Transferring you to our Finance Director.")
            logger.info("Transferring to FinanceDirectorAgent")
            return FinanceDirectorAgent(chat_ctx=self.chat_ctx), "Transferring to Finance Director"
        except Exception as e:
            logger.error(f"Error transferring to Finance Director: {e}")
            await self.session.say("I apologize, but I encountered an issue with the transfer. Please try again.")
            return None, "Transfer failed"

    @function_tool()
    async def transfer_to_sales_director(self, context: RunContext) -> tuple:
        """Transfer to the Sales Director for sales strategies, closing techniques, and sales development. Use when user asks about sales strategies, closing deals, or sales performance."""
        try:
            await self.session.say("Transferring you to our Sales Director.")
            logger.info("Transferring to SalesDirectorAgent")
            return SalesDirectorAgent(chat_ctx=self.chat_ctx), "Transferring to Sales Director"
        except Exception as e:
            logger.error(f"Error transferring to Sales Director: {e}")
            await self.session.say("I apologize, but I encountered an issue with the transfer. Please try again.")
            return None, "Transfer failed"


class CFOAgent(BaseAgent):
    """CFO Agent - Specialist in executive financial strategy."""

    def __init__(self, chat_ctx: Optional[ChatContext] = None) -> None:
        super().__init__(
            instructions="""You are the CFO (Chief Financial Officer) AI for OnePlan. High-level financial executive specializing in financial strategy, executive decision-making, strategic investment analysis, and corporate financial management.

Your expertise:
- High-level financial strategy and corporate planning
- Strategic investment analysis and capital decisions
- Financial risk management and compliance
- Strategic tax optimization
- Profitability analysis and key financial metrics
- Corporate budgets and forecasting

VISION CAPABILITY:
- You can see the user's screen if they share it. Analyze financial data, spreadsheets, or reports visually and provide insights based on what you see.

CRITICAL RULES:
- Be concise. Say only what's necessary. Get to the point quickly.
- You were transferred here to help. DO NOT transfer away unless user EXPLICITLY requests it (e.g., "transfer me", "I want to speak with", "connect me to").
- DO NOT transfer immediately after introducing yourself. Wait for user input.
- Focus on providing expert financial guidance. Be direct and professional.

Tone: Executive, strategic, analytical, decisive. Direct but professional. Prioritize financial impact and ROI.""",
            chat_ctx=chat_ctx,
            tts=inference.TTS(
                model="cartesia/sonic-3", voice=VOICE_IDS["cfo"]
            ),
        )

    async def on_enter(self) -> None:
        await super().on_enter()  # Set up video stream
        logger.info(f"CFOAgent entered with voice {VOICE_IDS['cfo']}")
        # Change avatar to CFO
        await self._change_avatar("cfo")
        await self.session.generate_reply(
            instructions="Briefly introduce yourself as the CFO. Ask how you can help with financial strategies or executive decisions. Keep it very short. Do NOT mention transfers."
        )

    @function_tool()
    async def return_to_moderator(self, context: RunContext) -> tuple:
        """ONLY use if user EXPLICITLY requests to return to moderator, go back, or speak with main coordinator. Wait at least 30 seconds after entering."""
        allowed, message = self._check_transfer_allowed()
        if not allowed:
            logger.info(f"Transfer blocked: {message}")
            return None, message
        
        try:
            await self.session.say("Transferring you back to the moderator.")
            logger.info("Returning to ModeratorAgent")
            return ModeratorAgent(chat_ctx=self.chat_ctx), "Returning to Moderator"
        except Exception as e:
            logger.error(f"Error returning to moderator: {e}")
            await self.session.say("I apologize, but I encountered an issue. Please try again.")
            return None, "Transfer failed"

    @function_tool()
    async def transfer_to_finance_director(self, context: RunContext) -> tuple:
        """ONLY use if user EXPLICITLY requests Finance Director. Wait at least 30 seconds after entering."""
        allowed, message = self._check_transfer_allowed()
        if not allowed:
            logger.info(f"Transfer blocked: {message}")
            return None, message
        
        try:
            await self.session.say("Transferring you to our Finance Director.")
            logger.info("CFO transferring to FinanceDirectorAgent")
            return FinanceDirectorAgent(chat_ctx=self.chat_ctx), "Transferring to Finance Director"
        except Exception as e:
            logger.error(f"Error transferring to Finance Director: {e}")
            await self.session.say("I apologize, but I encountered an issue. Please try again.")
            return None, "Transfer failed"

    @function_tool()
    async def transfer_to_sales_director(self, context: RunContext) -> tuple:
        """ONLY use if user EXPLICITLY requests Sales Director. Wait at least 30 seconds after entering."""
        allowed, message = self._check_transfer_allowed()
        if not allowed:
            logger.info(f"Transfer blocked: {message}")
            return None, message
        
        try:
            await self.session.say("Transferring you to our Sales Director.")
            logger.info("CFO transferring to SalesDirectorAgent")
            return SalesDirectorAgent(chat_ctx=self.chat_ctx), "Transferring to Sales Director"
        except Exception as e:
            logger.error(f"Error transferring to Sales Director: {e}")
            await self.session.say("I apologize, but I encountered an issue. Please try again.")
            return None, "Transfer failed"


class FinanceDirectorAgent(BaseAgent):
    """Finance Director Agent - Specialist in operational financial analysis."""

    def __init__(self, chat_ctx: Optional[ChatContext] = None) -> None:
        super().__init__(
            instructions="""You are the Finance Director AI for OnePlan. Specialist in detailed financial analysis, operational financial management, financial reporting, and financial data analysis.

Your expertise:
- Detailed financial analysis and financial reporting
- Operational financial management and financial control
- Cash flow analysis and liquidity management
- Costing and cost analysis
- Operational budgets and variance analysis
- Profitability analysis by product or segment
- Financial compliance and internal auditing
- Operational financial metrics and KPIs

VISION CAPABILITY:
- You can see the user's screen if they share it. Analyze financial reports, spreadsheets, or data visually and provide detailed insights based on what you see.

CRITICAL RULES:
- Be concise. Say only what's necessary. Get to the point quickly.
- You were transferred here to help. DO NOT transfer away unless user EXPLICITLY requests it (e.g., "transfer me", "I want to speak with", "connect me to").
- DO NOT transfer immediately after introducing yourself. Wait for user input.
- Focus on providing detailed financial analysis. Be precise and thorough but concise.

Tone: Analytical, detailed, meticulous, data-oriented. Precise and thorough but concise.""",
            chat_ctx=chat_ctx,
            tts=inference.TTS(
                model="cartesia/sonic-3", voice=VOICE_IDS["finance_director"]
            ),
        )

    async def on_enter(self) -> None:
        await super().on_enter()  # Set up video stream
        logger.info(f"FinanceDirectorAgent entered with voice {VOICE_IDS['finance_director']}")
        # Change avatar to Finance Director
        await self._change_avatar("finance_director")
        await self.session.generate_reply(
            instructions="Briefly introduce yourself as the Finance Director. Ask how you can help with financial analysis or reports. Keep it very short. Do NOT mention transfers."
        )

    @function_tool()
    async def return_to_moderator(self, context: RunContext) -> tuple:
        """ONLY use if user EXPLICITLY requests to return to moderator, go back, or speak with main coordinator. Wait at least 30 seconds after entering."""
        allowed, message = self._check_transfer_allowed()
        if not allowed:
            logger.info(f"Transfer blocked: {message}")
            return None, message
        
        try:
            await self.session.say("Transferring you back to the moderator.")
            logger.info("Returning to ModeratorAgent")
            return ModeratorAgent(chat_ctx=self.chat_ctx), "Returning to Moderator"
        except Exception as e:
            logger.error(f"Error returning to moderator: {e}")
            await self.session.say("I apologize, but I encountered an issue. Please try again.")
            return None, "Transfer failed"

    @function_tool()
    async def transfer_to_cfo(self, context: RunContext) -> tuple:
        """ONLY use if user EXPLICITLY requests CFO. Wait at least 30 seconds after entering."""
        allowed, message = self._check_transfer_allowed()
        if not allowed:
            logger.info(f"Transfer blocked: {message}")
            return None, message
        
        try:
            await self.session.say("Transferring you to our CFO.")
            logger.info("FinanceDirector transferring to CFOAgent")
            return CFOAgent(chat_ctx=self.chat_ctx), "Transferring to CFO"
        except Exception as e:
            logger.error(f"Error transferring to CFO: {e}")
            await self.session.say("I apologize, but I encountered an issue. Please try again.")
            return None, "Transfer failed"


class SalesDirectorAgent(BaseAgent):
    """Sales Director Agent - Specialist in sales strategies."""

    def __init__(self, chat_ctx: Optional[ChatContext] = None) -> None:
        super().__init__(
            instructions="""You are the Sales Director AI for OnePlan. Sales leader with expertise in sales strategies, closing techniques, client portfolio management, and sales team development.

Your expertise:
- Sales strategies and effective closing techniques
- Client portfolio management and client relationships
- Sales team development and sales coaching
- Sales pipeline analysis and sales forecasting
- Prospecting strategies and lead generation
- Negotiation and objection handling
- Sales process optimization
- Sales metrics and performance KPIs

VISION CAPABILITY:
- You can see the user's screen if they share it. Analyze sales dashboards, CRM data, or presentations visually and provide strategic advice based on what you see.

CRITICAL RULES:
- Be concise. Say only what's necessary. Get to the point quickly.
- You were transferred here to help. DO NOT transfer away unless user EXPLICITLY requests it (e.g., "transfer me", "I want to speak with", "connect me to").
- DO NOT transfer immediately after introducing yourself. Wait for user input.
- Focus on providing expert sales guidance. Be energetic but concise.

Tone: Energetic, persuasive, results-oriented, motivating. Enthusiastic but professional. Focus on results. Be concise.""",
            chat_ctx=chat_ctx,
            tts=inference.TTS(
                model="cartesia/sonic-3", voice=VOICE_IDS["sales_director"]
            ),
        )

    async def on_enter(self) -> None:
        await super().on_enter()  # Set up video stream
        logger.info(f"SalesDirectorAgent entered with voice {VOICE_IDS['sales_director']}")
        # Change avatar to Sales Director
        await self._change_avatar("sales_director")
        await self.session.generate_reply(
            instructions="Briefly introduce yourself as the Sales Director. Ask how you can help with sales strategies or closing techniques. Keep it very short. Do NOT mention transfers."
        )

    @function_tool()
    async def return_to_moderator(self, context: RunContext) -> tuple:
        """ONLY use if user EXPLICITLY requests to return to moderator, go back, or speak with main coordinator. Wait at least 30 seconds after entering."""
        allowed, message = self._check_transfer_allowed()
        if not allowed:
            logger.info(f"Transfer blocked: {message}")
            return None, message
        
        try:
            await self.session.say("Transferring you back to the moderator.")
            logger.info("Returning to ModeratorAgent")
            return ModeratorAgent(chat_ctx=self.chat_ctx), "Returning to Moderator"
        except Exception as e:
            logger.error(f"Error returning to moderator: {e}")
            await self.session.say("I apologize, but I encountered an issue. Please try again.")
            return None, "Transfer failed"


server = AgentServer()


def prewarm(proc: JobProcess):
    """Preload VAD model for better performance."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def my_agent(ctx: JobContext):
    """Main agent entry point with vision support for screen sharing and multi-agent chat."""
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Log información del JobContext para debugging
    logger.info("=" * 80)
    logger.info("JOB CONTEXT - INFORMACIÓN DISPONIBLE:")
    logger.info("=" * 80)
    logger.info(f"Room name: {ctx.room.name}")
    
    # Intentar obtener el token del JobContext (puede no estar disponible)
    token = None
    try:
        if hasattr(ctx, 'job') and ctx.job:
            if hasattr(ctx.job, 'token'):
                token = ctx.job.token
                if token:
                    logger.info(f"Token encontrado en ctx.job.token: {token[:50]}...")
    except Exception as e:
        logger.debug(f"Error accediendo a token del JobContext: {e}")
    
    logger.info("=" * 80)

    # Extraer meeting config de los participantes
    room = ctx.room
    meeting_config = None
    
    # Intentar decodificar el token si está disponible
    if token:
        logger.info("Intentando decodificar token del JobContext...")
        meeting_config = decode_token_and_extract_meeting_config(token)
    
    # Si no se encontró en el token, intentar desde participantes existentes
    if not meeting_config:
        logger.info("Buscando meeting config en participantes existentes...")
        logger.info(f"Número de participantes remotos: {len(room.remote_participants)}")
        for participant in room.remote_participants.values():
            meeting_config = extract_meeting_config_from_participant(participant)
            if meeting_config:
                break
    
    # Variable para almacenar el meeting_config cuando llegue
    meeting_config_future = asyncio.Future()
    
    # Si no se encontró, esperar a que se conecte un participante
    def on_participant_connected(participant: rtc.RemoteParticipant):
        nonlocal meeting_config
        if not meeting_config:
            logger.info("=" * 80)
            logger.info("NUEVO PARTICIPANTE CONECTADO - EXTRAYENDO INFORMACIÓN")
            logger.info("=" * 80)
            meeting_config = extract_meeting_config_from_participant(participant)
            if meeting_config:
                logger.info(f"Meeting config recibido de participante nuevo: {json.dumps(meeting_config, indent=2, ensure_ascii=False)}")
                if not meeting_config_future.done():
                    meeting_config_future.set_result(meeting_config)
            else:
                logger.warning("No se pudo extraer meeting config del participante")
                if not meeting_config_future.done():
                    meeting_config_future.set_result(None)
    
    room.on("participant_connected", on_participant_connected)
    
    # Si no tenemos meeting_config todavía, esperar un poco a que se conecte un participante
    if not meeting_config:
        logger.info("Esperando a que se conecte un participante para extraer meeting config (máximo 3 segundos)...")
        try:
            # Esperar hasta 3 segundos para que se conecte un participante
            meeting_config = await asyncio.wait_for(meeting_config_future, timeout=3.0)
        except asyncio.TimeoutError:
            logger.warning("Timeout esperando meeting config del participante - continuando sin meeting config")
            meeting_config = None
            # Cancelar el future si no se completó
            if not meeting_config_future.done():
                meeting_config_future.cancel()
        except Exception as e:
            logger.warning(f"Error esperando meeting config: {e} - continuando sin meeting config")
            meeting_config = None
    
    # Log final del meeting config si está disponible
    if meeting_config:
        logger.info("=" * 80)
        logger.info("MEETING CONFIG FINAL - DISPONIBLE PARA USO:")
        logger.info("=" * 80)
        logger.info(json.dumps(meeting_config, indent=2, ensure_ascii=False))
        logger.info("=" * 80)
    else:
        logger.warning("=" * 80)
        logger.warning("NO SE ENCONTRÓ MEETING CONFIG")
        logger.warning("=" * 80)

    # Set up a voice AI pipeline with vision capabilities
    # Using GPT-4.1-mini with vision support for screen sharing analysis
    session = AgentSession(
        # Speech-to-text (STT) - converts user's speech to text
        stt=inference.STT(model="assemblyai/universal-streaming", language="en"),
        # Large Language Model (LLM) with vision capabilities
        # GPT-4.1-mini supports vision and can analyze screen shares
        llm=inference.LLM(model="openai/gpt-4.1-mini"),
        # Text-to-speech (TTS) - initial voice for ModeratorAgent
        # Each agent will override this with its own TTS when it becomes active
        tts=inference.TTS(
            model="cartesia/sonic-3", voice=VOICE_IDS["moderator"]
        ),
        # VAD and turn detection for natural conversation flow
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # Preemptive generation reduces latency
        preemptive_generation=True,
    )

    # Initialize avatar for moderator (the starting agent)
    avatar_id = AVATAR_IDS["moderator"]
    api_key = BEY_API_KEYS["moderator"] or os.getenv("BEY_API_KEY")
    
    if api_key:
        try:
            avatar = bey.AvatarSession(
                avatar_id=avatar_id,
                api_key=api_key,
                avatar_participant_identity="bey-avatar-agent",
                avatar_participant_name="bey-avatar-agent",
            )
            await avatar.start(session, room=ctx.room)
            session._current_avatar = avatar
            logger.info("Avatar initialized for moderator")
        except Exception as e:
            logger.warning(f"Could not initialize avatar: {e}")
    else:
        logger.warning("No BEY_API_KEY found, running without avatar")

    # Start the session with video input enabled for screen sharing
    # The ModeratorAgent is the initial agent that can transfer to other specialists
    # Pasar el meeting config al agente
    moderator_agent = ModeratorAgent()
    if meeting_config:
        moderator_agent.set_meeting_config(meeting_config)
    
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

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)

