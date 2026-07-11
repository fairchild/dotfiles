# Vocal Skill Architecture

## Overview

Three tiers of voice integration for Claude Code, each building on the last. A local web console sits beside Tier 1 as a preference-tuning surface over the same provider scripts.

```
Tier 1: Voice Scripts          Tier 2: Voice Mode           Tier 3: Voice Bridge
(tools + web console)          (team-based loop)            (standalone process)

┌─────────────────┐           ┌──────────────────┐         ┌──────────────────┐
│ tts_local.py    │           │ Main Session     │         │ voice_bridge.py  │
│ tts_elevenlabs  │           │   ↕ SendMessage  │         │   mic → STT      │
│ stt_local.py    │           │ Voice Listener   │         │   → Claude CLI   │
│ stt_elevenlabs  │           │   (background)   │         │   → TTS → speak  │
│ web_console.py  │           │                  │         │                  │
└─────────────────┘           └──────────────────┘         └──────────────────┘
User-initiated                Agent-initiated               Continuous loop
"speak this" / "listen"       push when idle                hands-free conversation
```

## Tier 1: Voice Scripts

Standalone Python scripts following the image-gen skill pattern. Claude calls them via Bash tool.

| Script | Provider | Deps | Latency | Cost |
|--------|----------|------|---------|------|
| `tts_local.py` | macOS `say` | None (stdlib) | Instant | Free |
| `tts_elevenlabs.py` | ElevenLabs Flash v2.5 | `elevenlabs`, `httpx` | ~75ms | API |
| `stt_local.py` | mlx-whisper | `mlx-whisper`, `sounddevice` | ~500-2000ms | Free |
| `stt_elevenlabs.py` | ElevenLabs Scribe v2 | `elevenlabs`, `sounddevice` | ~150ms | API |
| `web_console.py` | Local browser UI | stdlib only | Interactive | Free |

Each script:
- Uses PEP 723 uv inline deps
- Has `--check` flag to validate config
- Prints output to stdout (text for STT, file path for TTS with `--output`)
- Logs to stderr
- Matches image-gen conventions exactly

### Local web console

`web_console.py` hosts http://127.0.0.1:8765 by default. It exposes a browser workbench for comparing local `say` and ElevenLabs TTS, recording or uploading audio for STT, running provider checks, and saving personal defaults.

The console intentionally calls the same scripts as the command-line workflow. Provider behavior stays centralized in `tts_local.py`, `stt_local.py`, `tts_elevenlabs.py`, and `stt_elevenlabs.py`; the web layer owns only preference persistence, HTTP upload/download handling, and the UI.

Saved preferences live in `skills/vocal/data/preferences.json` by default and are gitignored. Set `VOCAL_DATA_DIR` to keep them outside the skill checkout.

## Tier 2: Voice Mode (Team + SendMessage)

Uses Claude Code's team mechanism to create a background voice listener.

```
Main Session                     Voice Listener Agent (background)
     │                                      │
     │──── TeamCreate("vocal") ────────────▶│
     │──── Task(vocal-listener) ───────────▶│
     │                                      │
     │  ┌──────────────────────────────────▶│ runs stt script (blocking Bash)
     │  │                                   │ waits for speech...
     │  │                                   │
     │  │       SendMessage ◀───────────────│ speech detected + transcribed
     │  │                                   │
     │◀─┘  message arrives as new turn      │
     │                                      │
     │  Claude processes voice input        │
     │  Calls TTS script to speak response  │
     │  Sends "keep listening" ────────────▶│
     │                                      │ loops back to mic capture
     │         ... repeat ...               │
```

**Why this works**: Team SendMessage delivers messages as new conversation turns when the main session is idle (waiting for user input). Messages queue if mid-turn.

**Limitations**:
- Each listen cycle = one agent API call
- Bash timeout max 600s (10 min) per iteration
- Turn-based, not real-time duplex

## Tier 3: Voice Bridge (standalone process)

Wraps Claude CLI in `--print --input-format stream-json --output-format stream-json` mode for continuous voice conversation. See `backlog/voice-bridge-plan.md` for full design.

```
voice_bridge.py
  ├── mic → STT engine (streaming)
  ├── transcript → Claude CLI stdin (stream-json)
  ├── Claude stdout → response text
  └── response → TTS engine → speaker
```

**Latency budget** (ElevenLabs): ~750ms–3.2s end-to-end
**Latency budget** (local): ~1–5s end-to-end

## ElevenLabs API Reference

### Text-to-Speech Models

| Model | ID | Latency | Languages | Use Case |
|-------|-----|---------|-----------|----------|
| Flash v2.5 | `eleven_flash_v2_5` | ~75ms | 32 | Real-time, conversation |
| Turbo v2.5 | `eleven_turbo_v2_5` | ~250ms | 32 | Interactive, quality |
| Multilingual v2 | `eleven_multilingual_v2` | Higher | 29 | Long-form, narration |
| v3 | `eleven_v3` | Higher | 74 | Maximum expressiveness |

### Pre-made Voices

George, Sarah, Daniel, Charlotte (use name or voice ID). Custom voices via dashboard.

### Speech-to-Text

- **Scribe v2**: ~150ms latency, 90+ languages, batch + streaming
- WebSocket API handles voice activity detection server-side
- Files >8 min auto-chunked into 4 concurrent segments

### SDKs

- Python: `pip install elevenlabs`
- JavaScript: `npm install @elevenlabs/elevenlabs-js` (bun-compatible)
- Env var: `ELEVENLABS_API_KEY`

### Key Features

- **WebSocket streaming**: bidirectional for both TTS and STT
- **Chunk length schedule**: tunable for perceived latency
- **Latency optimization**: 0-4 scale (higher = faster, slight quality loss)

## Claude Code Background Communication Research

Comprehensive research into whether background processes can interrupt a foreground Claude Code session.

### Mechanisms Tested

| Mechanism | Can Interrupt? | Why |
|-----------|---------------|-----|
| Hooks (PreToolUse, PostToolUse, etc.) | No | Reactive — fire in response to events, can't initiate |
| MCP Servers | No | Passive tool providers — Claude must call them |
| Background Agents (Task tool) | No | Must be invoked by main session |
| **Team SendMessage** | **Yes, when idle** | Messages arrive as new turns when session waits for input |
| `UserPromptSubmit` hook | No | Only fires when user submits, can add context but not initiate |
| `Notification` hook | Unclear | Fires on notifications but can't inject messages |
| stdin injection | No | Interactive TUI doesn't accept external stdin |
| stream-json protocol | N/A | Different mode — `claude --print` only, not interactive |
| Agent SDK | Possible | Can resume sessions programmatically |
| macOS automation | Yes | AppleScript/keystroke injection — hacky but works |

### Key Architecture Insight

Claude Code is **session-centric and event-driven, not event-push**. All activity is organized around active sessions. Background work happens in separate sessions (e.g., `claude --agent name`). There is no mechanism to inject into a running interactive session.

The two viable paths for voice-driven interaction:
1. **Team SendMessage** — native, delivers when idle, good for turn-based voice
2. **stream-json wrapper** — programmatic, continuous, requires separate process

### Hooks Detail

- **PreToolUse**: runs before tool, can add `additionalContext` or `updatedInput`, can `allow`/`deny`/`ask`
- **PostToolUse**: runs after tool, can add `additionalContext`, can `block` (feedback, not prevention)
- **Stop**: runs when session ends, cleanup only
- **SessionStart**: runs once at session start, can set env vars
- **Notification**: fires on notifications, limited documentation
- All hooks receive JSON via stdin, return JSON via stdout, run in subprocess isolation

### Claude CLI Programmatic Modes

```bash
# Stream-json: bidirectional JSON streaming
claude --print --input-format stream-json --output-format stream-json

# Replay user messages for acknowledgment
claude --print --input-format stream-json --output-format stream-json --replay-user-messages

# Partial message streaming
claude --print --output-format stream-json --include-partial-messages

# Resume session
claude --print --resume SESSION_ID
```

## External Links

- [ElevenLabs TTS docs](https://elevenlabs.io/docs/overview/capabilities/text-to-speech)
- [ElevenLabs STT/Scribe](https://elevenlabs.io/realtime-speech-to-text)
- [ElevenLabs WebSocket streaming](https://elevenlabs.io/docs/developers/websockets)
- [ElevenLabs latency optimization](https://elevenlabs.io/docs/developers/best-practices/latency-optimization)
- [ElevenLabs skills repo](https://github.com/elevenlabs/skills)
- [ElevenLabs JS SDK](https://github.com/elevenlabs/elevenlabs-js)
- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference)
- [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Claude Code hooks docs](https://code.claude.com/docs/en/hooks)
