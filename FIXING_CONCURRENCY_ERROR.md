# Fixing Beyond Presence Concurrency Limit Error

## Problem

You're receiving a `429` error from Beyond Presence:
```
"You have reached your concurrency limit. Please upgrade your plan or stop other ongoing sessions."
```

This happens when multiple avatar sessions are active at the same time, exceeding your Beyond Presence plan's concurrency limit.

## Solution Implemented

The code has been updated to:

1. **Properly close previous avatar sessions** - The current avatar is fully closed before starting a new one
2. **Reuse participant identity** - All avatares use the same participant identity (`bey-avatar-agent`) to reuse the same participant slot
3. **Add delay between changes** - A small delay (0.5 seconds) ensures the previous session is fully closed
4. **Better error handling** - If avatar change fails, the agent transfer continues without failing completely

## Key Changes

### Before
- Each avatar used a unique participant identity
- Avatares weren't properly closed before creating new ones
- Multiple avatar sessions could be active simultaneously

### After
- All avatares use the same participant identity (`bey-avatar-agent`)
- Previous avatar is properly closed with `aclose()` before starting a new one
- Small delay ensures complete closure
- Errors in avatar change don't break agent transfers

## How It Works Now

1. **Avatar Change Process**:
   ```
   Current Avatar → Close (aclose) → Wait 0.5s → Start New Avatar
   ```

2. **Participant Reuse**:
   - All avatares use identity: `bey-avatar-agent`
   - This reuses the same participant slot in the room
   - Prevents multiple concurrent sessions

3. **Error Recovery**:
   - If avatar change fails, the agent transfer still completes
   - The agent will work, just without the avatar change
   - Logs will show the error for debugging

## Additional Steps to Fix

### 1. Stop All Active Sessions

If you still have active sessions:

1. **Check your Beyond Presence dashboard** - Look for active sessions
2. **Stop any running sessions** - Manually stop them from the dashboard
3. **Wait a few minutes** - Let the sessions fully terminate
4. **Restart your agent** - Try again

### 2. Check Your Plan Limits

1. **Review your Beyond Presence plan** - Check your concurrency limit
2. **Upgrade if needed** - If you need multiple concurrent sessions
3. **Or use one avatar at a time** - The current implementation ensures only one avatar is active

### 3. Monitor Logs

Watch for these log messages:
- `"Current avatar stopped successfully"` - Good, avatar closed properly
- `"Avatar successfully changed to {agent_key}"` - Good, new avatar started
- `"Error stopping current avatar"` - Warning, but continues
- `"Error starting new avatar"` - Error, but agent continues

## Testing

After the fix, test avatar changes:

1. **Start with moderator** - Should work normally
2. **Transfer to CFO** - Avatar should change
3. **Transfer to Sales Director** - Avatar should change again
4. **Return to moderator** - Avatar should change back

If you still see 429 errors:

1. **Wait longer between transfers** - Add more delay if needed
2. **Check for other active sessions** - Stop them first
3. **Verify avatar IDs** - Make sure all IDs are valid
4. **Check API key** - Ensure `BEY_API_KEY` is correct

## Code Changes Summary

### Main Fix: `_change_avatar()` method

```python
# Now properly closes previous avatar
if hasattr(current_avatar, "aclose"):
    await current_avatar.aclose()
await asyncio.sleep(0.5)  # Wait for closure

# Reuses same participant identity
new_avatar = bey.AvatarSession(
    avatar_id=AVATAR_IDS[agent_key],
    avatar_participant_identity="bey-avatar-agent",  # Same for all
    ...
)
```

### Initial Avatar Setup

```python
# Also uses consistent identity
avatar = bey.AvatarSession(
    avatar_id=AVATAR_IDS["moderator"],
    avatar_participant_identity="bey-avatar-agent",  # Consistent
    ...
)
```

## If Problems Persist

1. **Increase delay** - Change `await asyncio.sleep(0.5)` to `await asyncio.sleep(1.0)`
2. **Check Beyond Presence status** - Verify your account and API key
3. **Contact Beyond Presence support** - If you believe it's a service issue
4. **Consider alternative approach** - Use a single avatar for all agents (simpler but less visual variety)

## Alternative: Single Avatar Approach

If concurrency continues to be an issue, you can use a single avatar for all agents:

```python
# In _change_avatar, just update the avatar_id without creating new session
# This requires Beyond Presence to support dynamic avatar_id changes
# (May not be supported - check Beyond Presence docs)
```

Or simply use one avatar for all agents and only change the voice (TTS), which is already implemented and doesn't require multiple avatar sessions.

