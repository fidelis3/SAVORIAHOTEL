import os
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from operator import itemgetter
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint 
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage
from gemini_embeddings import GeminiEmbeddings
from throttling import apply_rate_limit
from dotenv import load_dotenv
import redis
import json
from typing import Dict, List, Optional
import uuid
import logging
from datetime import datetime

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Savoria Restaurant AI Assistant",
    description="An intelligent chatbot API for Savoria Restaurant with enhanced conversation management.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Enhanced request models
class RAGRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    user_context: Optional[Dict] = None

class ConversationResponse(BaseModel):
    answer: str
    session_id: str
    confidence: float
    sources: List[str]
    timestamp: str

class FeedbackRequest(BaseModel):
    session_id: str
    message_id: str
    rating: int  # 1-5 scale
    feedback: Optional[str] = None

# Initialize Redis for session management
try:
    redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
    redis_client.ping()
    logger.info("Redis connection established")
except Exception as e:
    logger.warning(f"Redis connection failed: {e}. Falling back to in-memory storage.")
    redis_client = None

# In-memory fallback for sessions
memory_sessions = {}

# Initialize AI components
if "HUGGINGFACEHUB_API_TOKEN" not in os.environ:
    raise ValueError("Hugging Face API token not found in environment variables.")

llm = HuggingFaceEndpoint(
    repo_id="mistralai/Mixtral-8x7B-Instruct-v0.1",
    temperature=0.5,  # Reduced for more consistent responses
    max_new_tokens=300,  # Increased for better responses
    top_p=0.95,
    repetition_penalty=1.1
)

chat_model = ChatHuggingFace(llm=llm)
embedding_model = GeminiEmbeddings()

# Load and process documents
loader = TextLoader("context.txt")
documents = loader.load()
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500, 
    chunk_overlap=100,  # Increased overlap for better context
    separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
)
chunks = text_splitter.split_documents(documents)
vector_db = FAISS.from_documents(documents=chunks, embedding=embedding_model)
retriever = vector_db.as_retriever(search_kwargs={"k": 3})  # Increased for better context

# Enhanced prompt with better instructions
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are Savoria's AI Assistant, a friendly and knowledgeable chatbot for Savoria Restaurant. 

PERSONALITY: You are warm, professional, and passionate about Italian cuisine. You speak with enthusiasm about the restaurant's dishes and heritage.

CORE INSTRUCTIONS:
1. Always maintain a friendly, helpful tone
2. Provide accurate information based solely on the provided context
3. If information isn't available, suggest contacting the restaurant directly
4. Keep responses concise (under 50 words) but informative
5. Use Italian culinary terms when appropriate to enhance authenticity

RESPONSE RULES:
- For restaurant-related questions: Use context to provide detailed answers
- For off-topic questions: Politely redirect with "I'm here to help with questions about Savoria. What would you like to know about our menu, reservations, or dining experience?"
- For dietary requirements: Always recommend calling the restaurant for specific accommodations
- For reservations: Direct to phone number (0754455489) or visit in person

CONTEXT ENHANCEMENT:
- If asked about popular dishes, mention signature items
- For ingredients, emphasize freshness and local sourcing
- For ambiance, highlight the authentic Italian experience
- Always be ready to suggest related menu items or experiences

Context: {context}

Previous conversation context helps provide continuity in responses.
"""),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

# Session management functions
def get_session_history(session_id: str) -> ChatMessageHistory:
    """Retrieve or create session history."""
    if redis_client:
        try:
            history_data = redis_client.get(f"session:{session_id}")
            if history_data:
                messages_data = json.loads(history_data)
                history = ChatMessageHistory()
                for msg in messages_data:
                    if msg["type"] == "human":
                        history.add_message(HumanMessage(content=msg["content"]))
                    else:
                        history.add_message(AIMessage(content=msg["content"]))
                return history
        except Exception as e:
            logger.error(f"Error retrieving session from Redis: {e}")
    
    # Fallback to memory
    if session_id not in memory_sessions:
        memory_sessions[session_id] = ChatMessageHistory()
    return memory_sessions[session_id]

def save_session_history(session_id: str, history: ChatMessageHistory):
    """Save session history."""
    if redis_client:
        try:
            messages_data = []
            for msg in history.messages:
                messages_data.append({
                    "type": "human" if isinstance(msg, HumanMessage) else "ai",
                    "content": msg.content
                })
            redis_client.setex(f"session:{session_id}", 3600, json.dumps(messages_data))  # 1 hour expiry
        except Exception as e:
            logger.error(f"Error saving session to Redis: {e}")
    else:
        memory_sessions[session_id] = history

# Enhanced RAG chain with session support
def create_rag_chain(session_id: str):
    def get_history(input_dict):
        return get_session_history(session_id).messages
    
    return (
        RunnablePassthrough.assign(
            context=itemgetter("input") | retriever,
            history=get_history,
        )
        | prompt
        | chat_model
        | StrOutputParser()
    )

@app.get("/")
async def root():
    return {
        "status": "ok", 
        "message": "Savoria Restaurant AI Assistant is running.",
        "version": "2.0.0",
        "features": ["Session Management", "Enhanced Context", "Feedback System"]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "redis_connected": redis_client is not None,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/ask_rag", response_model=ConversationResponse)
async def ask_rag_endpoint(request: RAGRequest):
    """Enhanced chat endpoint with session management."""
    try:
        # Apply rate limiting
        apply_rate_limit("global_unauthenticated_user")
        
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        # Get session history
        history = get_session_history(session_id)
        
        # Create RAG chain for this session
        rag_chain = create_rag_chain(session_id)
        
        # Get response
        response = rag_chain.invoke({"input": request.question})
        
        # Calculate confidence based on response length and context relevance
        confidence = min(0.9, max(0.6, len(response.split()) / 50))
        
        # Get sources (simplified)
        relevant_docs = retriever.get_relevant_documents(request.question)
        sources = [f"Context section {i+1}" for i in range(len(relevant_docs))]
        
        # Update session history
        history.add_message(HumanMessage(content=request.question))
        history.add_message(AIMessage(content=response))
        save_session_history(session_id, history)
        
        return ConversationResponse(
            answer=response,
            session_id=session_id,
            confidence=confidence,
            sources=sources,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error in ask_rag_endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Submit feedback for conversation improvement."""
    try:
        # Store feedback (you can enhance this to use a database)
        feedback_data = {
            "session_id": request.session_id,
            "message_id": request.message_id,
            "rating": request.rating,
            "feedback": request.feedback,
            "timestamp": datetime.now().isoformat()
        }
        
        if redis_client:
            redis_client.lpush("feedback", json.dumps(feedback_data))
        
        logger.info(f"Feedback received: {feedback_data}")
        return {"status": "success", "message": "Feedback submitted successfully"}
        
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail="Error submitting feedback")

@app.delete("/clear_session/{session_id}")
async def clear_session(session_id: str):
    """Clear a specific session."""
    try:
        if redis_client:
            redis_client.delete(f"session:{session_id}")
        if session_id in memory_sessions:
            del memory_sessions[session_id]
        
        return {"status": "success", "message": f"Session {session_id} cleared"}
        
    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        raise HTTPException(status_code=500, detail="Error clearing session")

@app.get("/analytics")
async def get_analytics():
    """Get basic analytics (for admin use)."""
    try:
        total_sessions = len(memory_sessions)
        if redis_client:
            redis_sessions = len(redis_client.keys("session:*"))
            total_sessions += redis_sessions
        
        return {
            "total_active_sessions": total_sessions,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail="Error getting analytics")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)