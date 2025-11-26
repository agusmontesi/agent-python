# How to Change Between Avatars

This guide explains how the avatar switching system works in the OnePlan agent system.

## How Avatar Changes Work

The system automatically changes avatares when you transfer between agents. Here's how it works:

### Automatic Avatar Changes

1. **When you start a conversation**: The system starts with the **Moderator** avatar
2. **When you transfer to a specialist**: The avatar automatically changes to that specialist's avatar
3. **When you return to the moderator**: The avatar changes back to the moderator's avatar

### Example Flow

```
User starts conversation
    ↓
Moderator Agent (Moderator Avatar) 
    ↓
User asks: "I need financial strategy advice"
    ↓
Moderator transfers to CFO
    ↓
CFO Agent (CFO Avatar) - Avatar changes automatically!
    ↓
User asks: "Actually, I need sales help"
    ↓
CFO transfers back to Moderator
    ↓
Moderator Agent (Moderator Avatar) - Avatar changes back!
    ↓
Moderator transfers to Sales Director
    ↓
Sales Director Agent (Sales Director Avatar) - Avatar changes again!
```

## How to Test Avatar Changes

### Step 1: Configure Your Avatar IDs

First, make sure you have configured all avatar IDs in `src/agent.py`:

```python
AVATAR_IDS = {
    "moderator": "YOUR_MODERATOR_AVATAR_ID",
    "cfo": "YOUR_CFO_AVATAR_ID",
    "finance_director": "YOUR_FINANCE_DIRECTOR_AVATAR_ID",
    "sales_director": "YOUR_SALES_DIRECTOR_AVATAR_ID",
    "marketing_director": "YOUR_MARKETING_DIRECTOR_AVATAR_ID",
}
```

### Step 2: Start Your Agent

Run your agent:
```bash
uv run src/agent.py dev
```

### Step 3: Test Avatar Changes

1. **Start a conversation** - You should see the Moderator avatar
2. **Ask to transfer to a specialist**, for example:
   - "Transfer me to the CFO"
   - "I need to talk to the Sales Director"
   - "Connect me with the Finance Director"
3. **Watch the avatar change** - The avatar should automatically switch to the specialist's avatar
4. **Return to moderator** - Say "Go back to moderator" or "Return to moderator"
5. **Watch the avatar change back** - The avatar should return to the moderator's avatar

## How the Code Works

### Avatar Change Method

Each agent has a `_change_avatar()` method that:

1. **Stops the current avatar** - Closes the current avatar session
2. **Creates a new avatar** - Creates a new AvatarSession with the new avatar ID
3. **Starts the new avatar** - Starts the new avatar session
4. **Updates the reference** - Stores the new avatar in session userdata

### Code Location

The avatar change logic is in each agent class:

- `ModeratorAgent._change_avatar()` - Called when transferring to specialists
- `CFOAgent._change_avatar()` - Called when entering or returning to moderator
- `FinanceDirectorAgent._change_avatar()` - Called when entering or returning
- `SalesDirectorAgent._change_avatar()` - Called when entering or returning
- `MarketingDirectorAgent._change_avatar()` - Called when entering or returning

### When Avatar Changes Happen

Avatares change automatically in these situations:

1. **On agent transfer** - When `transfer_to_*` functions are called
2. **On agent entry** - When a new agent's `on_enter()` method is called
3. **On return to moderator** - When `return_to_moderator()` is called

## Troubleshooting

### Avatar Doesn't Change

If the avatar doesn't change, check:

1. **Avatar IDs are correct** - Verify all avatar IDs in `AVATAR_IDS` are valid
2. **Beyond Presence API key** - Make sure `BEY_API_KEY` is set in `.env.local`
3. **Logs** - Check the logs for error messages about avatar changes
4. **Avatar exists** - Verify the avatar IDs exist in your Beyond Presence account

### Avatar Changes But Shows Wrong Face

If the avatar changes but shows the wrong face:

1. **Check avatar IDs** - Make sure each agent has the correct avatar ID
2. **Verify in Beyond Presence** - Confirm the avatar IDs match your Beyond Presence avatares

### Multiple Avatares Appear

If you see multiple avatares at once:

1. **Check participant identities** - Each avatar should have a unique `avatar_participant_identity`
2. **Frontend filtering** - Your frontend should filter to show only the active avatar

## Frontend Considerations

In your frontend application, you need to:

1. **Identify the active avatar** - Look for the participant with `lk.publish_on_behalf` attribute
2. **Show only active avatar** - Hide or remove inactive avatar participants
3. **Update on participant changes** - Listen for participant join/leave events

### React Example

```typescript
const { agent, audioTrack, videoTrack } = useVoiceAssistant();
// This automatically gets the correct avatar tracks
```

### Manual Filtering

```typescript
// Find the active avatar worker
const avatarWorker = room.remoteParticipants.find(
  p => p.kind === Kind.Agent && 
       p.attributes['lk.publish_on_behalf'] === agent.identity
);

// Get video track from avatar worker
const videoTrack = avatarWorker?.videoTracks.values().next().value?.track;
```

## Testing Checklist

- [ ] All avatar IDs configured in `AVATAR_IDS`
- [ ] Beyond Presence API key set in `.env.local`
- [ ] Agent starts with moderator avatar
- [ ] Transfer to CFO changes avatar
- [ ] Transfer to Finance Director changes avatar
- [ ] Transfer to Sales Director changes avatar
- [ ] Transfer to Marketing Director changes avatar
- [ ] Return to moderator restores moderator avatar
- [ ] Voice changes with each agent (if configured)
- [ ] No errors in logs during avatar changes

## Next Steps

1. **Configure all avatar IDs** - Replace placeholders with real IDs
2. **Configure different voices** - Set different voice IDs for each agent
3. **Test each transfer** - Verify avatar changes work for all agents
4. **Update frontend** - Ensure your frontend properly displays the active avatar

