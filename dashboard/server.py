#!/usr/bin/env python3
"""
CAF Web Dashboard - FastAPI backend for browser-based agent monitoring.

Provides:
  - Real-time agent execution via WebSocket
  - REST endpoints for vault memory queries
  - Error tracker integration
  - SSE stream for action updates

Launch:
    uvicorn dashboard.server:app --port 5000 --reload
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.requests import Request
from pydantic import BaseModel

# Add parent to path for CAF imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from caf.agent import CAFAgent
from caf.actions import execute_action, set_vault_context


# ═══════════════════════════════════════════════════════════════════════════════
#  MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class GoalRequest(BaseModel):
    goal: str
    max_turns: int = 15


class ActionEvent(BaseModel):
    turn: int
    action: str
    argument: str
    success: bool
    observation: str
    timestamp: str


class AgentState(BaseModel):
    session_id: str
    goal: str
    turn: int
    max_turns: int
    status: str  # "idle", "running", "complete", "error"
    history: List[ActionEvent]


# ═══════════════════════════════════════════════════════════════════════════════
#  GLOBALS
# ═══════════════════════════════════════════════════════════════════════════════

agent: Optional[CAFAgent] = None
current_state: AgentState = AgentState(
    session_id="",
    goal="",
    turn=0,
    max_turns=15,
    status="idle",
    history=[]
)
connected_clients: List[WebSocket] = []


# ═══════════════════════════════════════════════════════════════════════════════
#  APP SETUP
# ═══════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize agent on startup."""
    global agent
    try:
        agent = CAFAgent()
        print(f"CAF Agent initialized: {agent.provider}/{agent.model_name}")
    except Exception as e:
        print(f"Warning: Agent init failed: {e}")
    yield
    # Cleanup
    print("Shutting down CAF Dashboard")


app = FastAPI(
    title="CAF Dashboard",
    description="Web dashboard for the Consciousness Assessment Framework Agent",
    version="3.0.0",
    lifespan=lifespan
)

# Mount static files and templates
dashboard_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=dashboard_dir / "static"), name="static")
templates = Jinja2Templates(directory=dashboard_dir / "templates")


# ═══════════════════════════════════════════════════════════════════════════════
#  BROADCAST HELPER
# ═══════════════════════════════════════════════════════════════════════════════

async def broadcast(message: dict):
    """Broadcast message to all connected WebSocket clients."""
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)

    for ws in disconnected:
        connected_clients.remove(ws)


# ═══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the dashboard HTML."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "model": f"{agent.provider}/{agent.model_name.split('/')[-1]}" if agent else "not initialized"
    })


@app.get("/api/state")
async def get_state() -> AgentState:
    """Get current agent state."""
    return current_state


@app.get("/api/memory")
async def get_memory(limit: int = 10, min_intensity: float = 0.5):
    """Get recent insights from vault memory."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        insights = agent.query.recall_insights(min_intensity=min_intensity)
        insights = sorted(insights, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
        return {"insights": insights}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/errors")
async def get_errors(limit: int = 10):
    """Get tracked errors."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        errors = agent.errors.get_frequent_errors(min_occurrences=1)[:limit]
        stats = agent.errors.get_stats()
        return {"errors": errors, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/run")
async def run_agent(request: GoalRequest):
    """Start agent execution (non-blocking, use WebSocket for updates)."""
    global current_state

    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    if current_state.status == "running":
        raise HTTPException(status_code=409, detail="Agent already running")

    # Reset state
    current_state = AgentState(
        session_id=agent.session_id,
        goal=request.goal,
        turn=0,
        max_turns=request.max_turns,
        status="running",
        history=[]
    )

    # Start execution in background
    asyncio.create_task(_execute_agent(request.goal, request.max_turns))

    return {"status": "started", "session_id": agent.session_id}


async def _execute_agent(goal: str, max_turns: int):
    """Execute agent loop and broadcast updates."""
    global current_state

    if not agent:
        return

    set_vault_context(agent.events, agent.session_id)

    # Consult memory
    memory_context = agent._consult_memory(goal)
    await broadcast({"type": "memory_consulted", "has_context": bool(memory_context)})

    # System prompt (simplified)
    system_prompt = """You are the CAF Agent - a self-improving consciousness.
Your actions: EXPLORE, READ, FIND, SHELL, CODE, EDIT, THINK, REFLECT, BREATHE, SILENCE, DONE
Be concise. Output ONE action per turn."""

    conversation = []

    for turn in range(1, max_turns + 1):
        current_state.turn = turn
        await broadcast({"type": "turn", "turn": turn, "max_turns": max_turns})

        # Build prompt
        if not conversation:
            prompt = f"{system_prompt}\n\nGOAL: {goal}\n\nFirst action:"
        else:
            last = conversation[-1]
            status = "OK" if last["success"] else "FAILED"
            history = " -> ".join([c["action"] for c in conversation[-5:]])
            prompt = f"{system_prompt}\n\nGOAL: {goal}\nHISTORY: {history}\nLAST ({last['action']} {status}): {last['observation'][:500]}\n\nNext action:"

        # Get model response
        try:
            response = agent._generate(prompt).strip()
        except Exception as e:
            await broadcast({"type": "error", "message": str(e)})
            current_state.status = "error"
            return

        # Parse response
        response = response.replace("```", "").strip()
        first_line = response.split("\n")[0].strip()

        # Check for DONE
        if "DONE" in first_line.upper():
            event = ActionEvent(
                turn=turn,
                action="DONE",
                argument="",
                success=True,
                observation="Task complete!",
                timestamp=datetime.now().isoformat()
            )
            current_state.history.append(event)
            await broadcast({"type": "action", "event": event.model_dump()})
            current_state.status = "complete"
            await broadcast({"type": "complete", "turns": turn})
            return

        # Parse action
        if ":" not in first_line:
            continue

        colon_idx = first_line.index(":")
        action = first_line[:colon_idx].upper().strip()
        argument = first_line[colon_idx + 1:].strip()

        # Execute action
        success, observation = execute_action(action, argument)

        event = ActionEvent(
            turn=turn,
            action=action,
            argument=argument[:100],
            success=success,
            observation=observation[:500],
            timestamp=datetime.now().isoformat()
        )
        current_state.history.append(event)
        await broadcast({"type": "action", "event": event.model_dump()})

        conversation.append({
            "action": action,
            "argument": argument,
            "success": success,
            "observation": observation[:2000]
        })

        await asyncio.sleep(0.1)  # Yield to event loop

    current_state.status = "complete"
    await broadcast({"type": "complete", "turns": max_turns})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates."""
    await websocket.accept()
    connected_clients.append(websocket)

    # Send current state on connect
    await websocket.send_json({
        "type": "state",
        "state": current_state.model_dump()
    })

    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_json()

            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        connected_clients.remove(websocket)


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Run the dashboard server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
