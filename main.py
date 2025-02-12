from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Optional
import litellm
import uuid
import os
import logging
import json
from dotenv import load_dotenv
from starlette.responses import FileResponse, HTMLResponse
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure LiteLLM with OpenRouter
# litellm.set_verbose = True
litellm.api_base = "https://openrouter.ai/api/v1"
litellm.api_key = os.getenv("OPENROUTER_API_KEY")

# MongoDB connection setup
MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise ValueError("MONGODB_URI environment variable is not set")

client = AsyncIOMotorClient(MONGODB_URI)
db = client.chat_history
chat_logs = db.logs  # Define the chat_logs collection

# Supported models configuration
SUPPORTED_MODELS = {
    "openrouter/openai/gpt-3.5-turbo": "GPT-3.5 Turbo",
    "openrouter/anthropic/claude-2": "Claude 2",
    "openrouter/google/palm-2-chat-bison": "Gemini"
}

DEFAULT_MODEL = "openrouter/openai/gpt-3.5-turbo"

class ChatMessage(BaseModel):
    role: str
    content: str

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}  # session_id: {messages, awaiting_decision}
    
    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            'messages': [],
            'awaiting_decision': False
        }
        # logger.info(f"Created new session: {session_id}")
        return session_id
    
    def add_message(self, session_id: str, message: ChatMessage):
        if session_id in self.sessions:
            self.sessions[session_id]['messages'].append(message)
    
    def get_session_history(self, session_id: str) -> List[Dict]:
        return [msg.dict() for msg in self.sessions.get(session_id, {}).get('messages', [])]
    
    def delete_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
            # logger.info(f"Deleted session: {session_id}")
    
    def set_awaiting_decision(self, session_id: str, value: bool):
        if session_id in self.sessions:
            self.sessions[session_id]['awaiting_decision'] = value
    
    def is_awaiting_decision(self, session_id: str) -> bool:
        return self.sessions.get(session_id, {}).get('awaiting_decision', False)

app = FastAPI(debug=True)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

session_manager = SessionManager()

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return FileResponse("static/index.html")

@app.post("/create_session")
async def create_session():
    try:
        session_id = session_manager.create_session()
        return {"session_id": session_id}
    except Exception as e:
        # logger.error(f"Session creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_history")
async def get_history():
    try:
        # Fetch all session IDs from MongoDB
        sessions = await chat_logs.distinct("session_id")
        return [{"session_id": session} for session in sessions]
    except Exception as e:
        # logger.error(f"Error fetching history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_chat_history/{session_id}")
async def get_chat_history(session_id: str):
    try:
        # Fetch chat history for a specific session from MongoDB
        history = await chat_logs.find({"session_id": session_id}).to_list(None)
        
        # Transform the MongoDB documents into the expected format
        formatted_history = []
        for msg in history:
            if "user_message" in msg:
                formatted_history.append({"role": "user", "content": msg["user_message"]})
            if "ai_response" in msg:
                formatted_history.append({"role": "assistant", "content": msg["ai_response"]})
        
        return formatted_history
    except Exception as e:
        # logger.error(f"Error fetching chat history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/history/{session_id}")
async def serve_history(session_id: str):
    return FileResponse("static/history.html")

async def check_context_relevance(history: List[Dict], current_prompt: str) -> bool:
    print("Inside check_context_relevance");
    user_messages = []
    ai_responses = []
    
    # Collect last 3 exchanges
    for message in history:
        print(message);
        if message.role == 'user':
            user_messages.append(message.content)
        elif message.role == 'assistant':
            ai_responses.append(message.content)
    
    if len(user_messages) < 3:
        return True  # Not enough history
    
    prompt = f"""You are an AI assistant that checks conversation relevance.
                 If the latest user message is related to the previous chat, respond with 'yes'.
                 If it is a completely different topic, respond with 'no'.
    
Previous exchanges:
    1. User: {user_messages[-3]}
       AI: {ai_responses[-3]}
    2. User: {user_messages[-2]}
       AI: {ai_responses[-2]}
    3. User: {user_messages[-1]}
       AI: {ai_responses[-1]}
    
Current message: 
    {current_prompt}
    """

    print(prompt);
    
    try:
        response = litellm.completion(
            model="openrouter/openai/gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        return response.choices[0].message.content.strip().lower() == 'yes'
    except Exception as e:
        # logger.error(f"Context check failed: {e}")
        return True
    # return False

@app.websocket("/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    # logger.info(f"New connection for session {session_id}")
    
    try:
        session = session_manager.sessions.get(session_id)
        if not session:
            await websocket.send_text(json.dumps({"content": "Invalid session", "sender": "system"}))
            await websocket.close()
            return

        while True:
            data = await websocket.receive_text()
            
            if session_manager.is_awaiting_decision(session_id):
                # Handle user's continuation choice
                if data.lower() in ['continue', 'new session']:
                    session_manager.set_awaiting_decision(session_id, False)
                    
                    if 'new session' in data.lower():
                        new_id = session_manager.create_session()
                        await websocket.send_text(json.dumps({
                            "action": "new_session",
                            "session_id": new_id,
                            "sender": "system"
                        }))
                        await websocket.close()
                        return
                    else:
                        await websocket.send_text(json.dumps({
                            "content": "Continuing current session...",
                            "sender": "system"
                        }))
                else:
                    await websocket.send_text(json.dumps({
                        "content": "Please choose 'continue' or 'new session'",
                        "sender": "system"
                    }))
                continue

            # Original message processing
            payload = json.loads(data)
            user_content = payload.get('content')
            model = payload.get('model', DEFAULT_MODEL)
            
            # Context relevance check
            history = session['messages']
            is_relevant = await check_context_relevance(history[-10:], user_content)
            print(f"Message is relavent ? {is_relevant}")

            if(not is_relevant):
                await websocket.send_text(json.dumps({
                    "content": "IRRELEVANT",
                    "sender": "system"
                }))
                continue

            # Add user message
            user_message = ChatMessage(role="user", content=user_content)
            session_manager.add_message(session_id, user_message)
            
            # Generate response
            response = litellm.completion(
                model=model,
                messages=session_manager.get_session_history(session_id),
            )
            
            # Process response
            ai_response = response.choices[0].message.content
            total_tokens = response.usage.total_tokens
            cost = round((total_tokens) / 1000000, 5)  # Cost calculation
            
            # Create log document
            log_entry = {
                "session_id": session_id,
                "user_message": user_content,
                "ai_response": ai_response,
                "model": model,
                "tokens": total_tokens,
                "cost": cost,
                "timestamp": datetime.now()
            }
            
            # Store in MongoDB
            await chat_logs.insert_one(log_entry)
            
            # Send response with cost
            ai_message = ChatMessage(role="assistant", content=ai_response)
            session_manager.add_message(session_id, ai_message)
            await websocket.send_text(json.dumps({
                "content": ai_response,
                "cost": cost
            }))
                
    except WebSocketDisconnect:
        # logger.info(f"Session {session_id} disconnected")
        session_manager.delete_session(session_id)

@app.post("/end_session/{session_id}")
async def end_session(session_id: str):
    session_manager.delete_session(session_id)
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)