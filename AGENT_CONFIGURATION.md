# OnePlan Agent Configuration

This project implements a system of 5 professional AI agents for OnePlan, each with their own personality and specialization.

## Available Agents

1. **ModeratorAgent** - Main coordinator and entry point
2. **CFOAgent** - Specialist in executive financial strategy
3. **FinanceDirectorAgent** - Specialist in operational financial analysis
4. **SalesDirectorAgent** - Specialist in sales strategies
5. **MarketingDirectorAgent** - Specialist in marketing strategies

## Avatar Configuration

### Step 1: Get Avatar IDs

1. Access your Beyond Presence account
2. Create or select 5 different avatars (one for each agent)
3. Copy the `avatar_id` of each avatar

### Step 2: Configure IDs in Code

Edit the `src/agent.py` file and replace the placeholders in the `AVATAR_IDS` dictionary:

```python
AVATAR_IDS = {
    "moderator": "YOUR_MODERATOR_AVATAR_ID",
    "cfo": "YOUR_CFO_AVATAR_ID",
    "finance_director": "YOUR_FINANCE_DIRECTOR_AVATAR_ID",
    "sales_director": "YOUR_SALES_DIRECTOR_AVATAR_ID",
    "marketing_director": "YOUR_MARKETING_DIRECTOR_AVATAR_ID",
}
```

### Step 3: Configure Voices (Optional)

For each agent to have a different voice, edit the `VOICE_IDS` dictionary in `src/agent.py`:

```python
VOICE_IDS = {
    "moderator": "VOICE_ID_MODERATOR",
    "cfo": "VOICE_ID_CFO",
    "finance_director": "VOICE_ID_FINANCE_DIRECTOR",
    "sales_director": "VOICE_ID_SALES_DIRECTOR",
    "marketing_director": "VOICE_ID_MARKETING_DIRECTOR",
}
```

You can find available voice IDs in the [Cartesia documentation](https://docs.livekit.io/agents/models/tts/).

## Dynamic Avatar and Voice Changes

The system now supports **dynamic avatar and voice changes** when transferring between agents:

- **Avatar changes**: When an agent transfers to another agent, the avatar automatically changes to match the new agent's avatar
- **Voice changes**: Each agent has its own configured voice, which changes automatically when the agent changes
- **Smooth transitions**: The system handles closing the current avatar and starting the new one seamlessly

### How It Works

1. When a transfer occurs, the current avatar is stopped
2. A new avatar with the corresponding agent's ID is started
3. The new agent's voice (TTS) is automatically used
4. The conversation context is preserved throughout the transfer

## Transfer System

Agents can transfer between each other using function tools:

- **ModeratorAgent** can transfer to any other specialized agent
- Each specialized agent can return to the **ModeratorAgent**

Transfers preserve conversation context using `chat_ctx`, so each agent has access to the complete conversation history.

## Usage

1. The user starts a conversation with the **ModeratorAgent**
2. The moderator can:
   - Answer general inquiries
   - Transfer to specialists when specific expertise is required
3. Specialized agents can:
   - Provide expert advice in their area
   - Transfer back to the moderator when appropriate

## Customization

### Instructions and Personality

Each agent has personalized instructions that define their personality and behavior. You can modify these instructions in the agent classes in `src/agent.py` to adjust:

- Tone and communication style
- Areas of specialization
- Specific behaviors and rules

### Different LLM Models per Agent

Each specialized agent (CFO, Finance Director, Sales Director, Marketing Director) can use a different LLM model if desired. To do this, modify the transfer calls in `ModeratorAgent`:

```python
@function_tool()
async def transfer_to_cfo(self, context: RunContext) -> tuple:
    """Transfer to the CFO..."""
    await self._change_avatar("cfo")
    await self.session.generate_reply(...)
    # Specify a different LLM model, for example:
    return CFOAgent(
        chat_ctx=self.session.chat_ctx,
        llm_model="openai/gpt-4o"  # Use a more powerful model for CFO
    ), "Transferring to CFO"
```

Available models:
- `openai/gpt-4.1-mini` (default, faster and more economical)
- `openai/gpt-4o` (more powerful, better for complex analysis)
- `openai/gpt-4-turbo` (balance between speed and power)
- Other models available at [LiveKit Agents Models](https://docs.livekit.io/agents/models/llm/)

## Language

All agents communicate in **English only**. The system is configured to use English for all conversations and agent instructions.

## Environment Variables

Make sure you have configured in your `.env.local` file:

```
BEY_API_KEY=your_beyond_presence_api_key
OPENAI_API_KEY=your_openai_api_key
LIVEKIT_URL=your_livekit_url
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_secret
```

