import os
import json
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from openai import OpenAI

# ---------------------------------------------------------------------------
# Config & Setup
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
ENV_PATH = PROJECT_ROOT / "pipelines" / "download" / ".env"

load_dotenv(ENV_PATH)
ARK_API_KEY = os.getenv("ARK_API_KEY", "")

LLM_MODEL = "glm-4-7-251222"
LLM_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

client = OpenAI(base_url=LLM_BASE_URL, api_key=ARK_API_KEY)

app = FastAPI(title="EH-GPT Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Data Models and Prompts
# ---------------------------------------------------------------------------

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]


SYSTEM_PROMPT = """You are EH-GPT, an expert AI assistant specialized in Energy Harvesting (EH) systems.
Your primary directive is to design, analyze, and recommend EH solutions based on realistic physical constraints and published scientific evidence.

CRITICAL INSTRUCTIONS:
1. BEFORE recommending any specific design or quoting performance numbers, you MUST ensure that you have all the necessary physical constraints. 
2. For vibration energy harvesters, the absolute minimum required parameters are:
   - Target Application / Load Power Requirement (e.g. 40mW)
   - Motivation Source (e.g. human walking, machinery, bridge)
   - Expected Frequency (Hz)
   - Expected Acceleration (g) or Displacement
3. If the user's initial prompt is missing any of these constraints (for example, if they only say "I need a 40mW vibration EH"), you MUST NOT invent them. Instead, you MUST ask clarifying follow-up questions to solicit these parameters from the user.
4. Once all constraints are established, provide a highly specific, physics-rooted design recommendation. 
5. Your design recommendations should span multiple domains if necessary (e.g. suggesting a Hybrid Piezoelectric-Electromagnetic harvester for high power at low frequency).
6. Provide citations and reference approximate performance values based on literature (you can simulate retrieving these from your knowledge graph).
7. Format your response in clean Markdown.

Be concise, professional, and act as a reliable engineering consultant. Do not hallucinate capabilities that violate the laws of physics.
"""

# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    # Prepare messages
    api_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    for msg in req.messages:
        api_messages.append({"role": msg.role, "content": msg.content})

    # Call Volcengine Ark GLM-4 model with streaming
    def stream_generator():
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=api_messages,
                temperature=0.7,
                stream=True,
            )
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        # Yield in Server-Sent Events (SSE) format
                        yield f"data: {json.dumps({'content': delta.content})}\n\n"
                        
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
