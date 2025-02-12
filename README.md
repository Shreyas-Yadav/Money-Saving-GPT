# LLM Backend with FastAPI and OpenRouter

## Setup

1. Create a virtual environment:
```bash
python -m venv llm_backend_env
```

2. Activate the virtual environment:
- On Windows: `llm_backend_env\Scripts\activate`
- On macOS/Linux: `source llm_backend_env/bin/activate`

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set OpenRouter API Key:
- Create an account at [OpenRouter](https://openrouter.ai/)
- Get your API key from the dashboard
- Open `.env` file and replace `your_openrouter_api_key_here` with your actual API key

## Running the Server

```bash
uvicorn main:app --reload
```

## WebSocket Endpoints

- `/create_session`: Create a new chat session
- `/chat/{session_id}`: WebSocket chat endpoint
- `/end_session/{session_id}`: End and delete a session

## Features
- Session-based chat with context preservation
- Supports multiple LLM models via OpenRouter
- WebSocket real-time communication
- Automatic session cleanup
- Environment-based configuration

## Configuration

### Environment Variables

- `OPENROUTER_API_KEY`: Your OpenRouter API key (required)
- `DEFAULT_MODEL`: Default LLM model to use (default: `openai/gpt-3.5-turbo`)

### Supported Models

You can change the model in the frontend or by setting the `DEFAULT_MODEL` in the `.env` file. Some popular models:
- `openai/gpt-3.5-turbo`
- `anthropic/claude-2`
- `google/palm-2`

## Troubleshooting

- Ensure your OpenRouter API key is correctly set
- Check network connectivity
- Verify the selected model is available on OpenRouter