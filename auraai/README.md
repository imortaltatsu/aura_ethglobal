# auraai

A Pipecat AI voice agent built with a cascade pipeline (STT → LLM → TTS).

## Configuration

- **Bot Type**: Web
- **Transport(s)**: SmallWebRTC
- **Pipeline**: Cascade
  - **STT**: Whisper (Local)
  - **LLM**: Ollama
  - **TTS**: OpenAI TTS
- **Features**:
  - Audio Recording
  - Transcription
  - smart-turn v3
  - Observability (Whisker + Tail)

## Setup

### Server

1. **Navigate to server directory**:

   ```bash
   cd server
   ```

2. **Install dependencies**:

   ```bash
   uv sync
   ```

3. **Configure environment variables**:

   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

4. **Run the bot**:

   - SmallWebRTC: `uv run bot.py`

### Client

1. **Navigate to client directory**:

   ```bash
   cd client
   ```

2. **Install dependencies**:

   ```bash
   npm install
   ```

3. **Configure environment variables**:

   ```bash
   cp env.example .env.local
   # Edit .env.local if needed (defaults to localhost:7860)
   ```

   > **Note:** Environment variables in Vite are bundled into the client and exposed in the browser. For production applications that require secret protection, consider implementing a backend proxy server to handle API requests and manage sensitive credentials securely.

4. **Run development server**:

   ```bash
   npm run dev
   ```

5. **Open browser**:

   http://localhost:5173

## Project Structure

```
auraai/
├── server/              # Python bot server
│   ├── bot.py           # Main bot implementation
│   ├── pyproject.toml   # Python dependencies
│   ├── env.example      # Environment variables template
│   ├── .env             # Your API keys (git-ignored)
│   └── ...
├── client/              # React application
│   ├── src/             # Client source code
│   ├── package.json     # Node dependencies
│   └── ...
├── .gitignore           # Git ignore patterns
└── README.md            # This file
```
## Observability

This project includes observability tools to help you debug and monitor your bot:

### Whisker - Live Pipeline Debugger

**Whisker** is a live graphical debugger that lets you visualize pipelines and debug frames in real time.

With Whisker you can:

- 🗺️ View a live graph of your pipeline
- ⚡ Watch frame processors flash in real time as frames pass through them
- 📌 Select a processor to inspect the frames it has handled
- 🔍 Filter frames by name to quickly find the ones you care about
- 🧵 Select a frame to trace its full path through the pipeline
- 💾 Save and load previous sessions for review and troubleshooting

**To use Whisker:**

1. Run an ngrok tunnel to expose your bot:

   ```bash
   ngrok http 9090
   ```

   > Tip: Use `--subdomain` for a repeatable ngrok URL

2. Navigate to [https://whisker.pipecat.ai/](https://whisker.pipecat.ai/) and enter your ngrok URL (e.g., `your-subdomain.ngrok.io`)

3. Once your bot is running, press connect

### Tail - Terminal Dashboard

**Tail** is a terminal dashboard that lets you monitor your Pipecat sessions in real time.

With Tail you can:

- 📜 Follow system logs in real time
- 💬 Track conversations as they happen
- 🔊 Monitor user and agent audio levels
- 📈 Keep an eye on service metrics and usage

**To use Tail:**

1. Run your bot (in one terminal)

2. Launch Tail in another terminal:
   ```bash
   pipecat tail
   ```
## Learn More

- [Pipecat Documentation](https://docs.pipecat.ai/)
- [Voice UI Kit Documentation](https://voiceuikit.pipecat.ai/)
- [Pipecat GitHub](https://github.com/pipecat-ai/pipecat)
- [Pipecat Examples](https://github.com/pipecat-ai/pipecat-examples)
- [Discord Community](https://discord.gg/pipecat)