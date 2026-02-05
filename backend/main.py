"""FastAPI backend for ROS2 web GUI."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ros_bridge import ros_bridge


class PublishRequest(BaseModel):
    """Request body for publishing a message."""
    msg_type: str
    data: dict


class WebSocketManager:
    """Manages WebSocket connections for topic subscriptions."""

    def __init__(self):
        self.connections: Dict[WebSocket, Set[str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.connections[websocket] = set()

    async def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection."""
        async with self._lock:
            if websocket in self.connections:
                topics = self.connections[websocket]
                for topic in topics:
                    ros_bridge.unsubscribe(topic)
                del self.connections[websocket]

    async def subscribe(self, websocket: WebSocket, topic: str) -> bool:
        """Subscribe a WebSocket to a topic."""
        async with self._lock:
            if websocket not in self.connections:
                return False

            def callback(topic_name: str, data: dict):
                asyncio.create_task(self._send_message(websocket, topic_name, data))

            success = ros_bridge.subscribe(topic, callback)
            if success:
                self.connections[websocket].add(topic)
            return success

    async def unsubscribe(self, websocket: WebSocket, topic: str) -> bool:
        """Unsubscribe a WebSocket from a topic."""
        async with self._lock:
            if websocket not in self.connections:
                return False

            if topic in self.connections[websocket]:
                self.connections[websocket].remove(topic)
                # Only fully unsubscribe if no other connections want this topic
                other_subs = any(topic in topics for ws, topics in self.connections.items() if ws != websocket)
                if not other_subs:
                    ros_bridge.unsubscribe(topic)
                return True
            return False

    async def _send_message(self, websocket: WebSocket, topic: str, data: dict):
        """Send a message to a WebSocket."""
        try:
            await websocket.send_json({
                'type': 'message',
                'topic': topic,
                'data': data,
            })
        except Exception:
            pass


ws_manager = WebSocketManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    ros_bridge.start()
    yield
    # Shutdown
    ros_bridge.stop()


app = FastAPI(title="ROS2 Web GUI", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# REST API endpoints

@app.get("/api/topics")
async def get_topics():
    """Get list of all topics with their message types."""
    topics = ros_bridge.get_topics()
    return [asdict(t) for t in topics]


@app.get("/api/topics/{topic:path}/type")
async def get_topic_type(topic: str):
    """Get message type definition for a topic."""
    topic_name = f"/{topic}" if not topic.startswith('/') else topic
    result = ros_bridge.get_topic_type(topic_name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Topic {topic_name} not found")
    return result


@app.post("/api/topics/{topic:path}/publish")
async def publish_message(topic: str, request: PublishRequest):
    """Publish a message to a topic."""
    topic_name = f"/{topic}" if not topic.startswith('/') else topic
    success = ros_bridge.publish(topic_name, request.msg_type, request.data)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to publish message")
    return {"status": "ok"}


@app.get("/api/nodes")
async def get_nodes():
    """Get list of all nodes."""
    nodes = ros_bridge.get_nodes()
    return [asdict(n) for n in nodes]


@app.get("/api/graph")
async def get_graph():
    """Get node graph data for visualization."""
    return ros_bridge.get_graph()


# WebSocket endpoint

@app.websocket("/ws/topics")
async def websocket_topics(websocket: WebSocket):
    """WebSocket endpoint for topic subscriptions."""
    await ws_manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get('action')
            topic = data.get('topic')

            if action == 'subscribe' and topic:
                success = await ws_manager.subscribe(websocket, topic)
                await websocket.send_json({
                    'type': 'subscription',
                    'topic': topic,
                    'status': 'subscribed' if success else 'failed'
                })

            elif action == 'unsubscribe' and topic:
                success = await ws_manager.unsubscribe(websocket, topic)
                await websocket.send_json({
                    'type': 'subscription',
                    'topic': topic,
                    'status': 'unsubscribed' if success else 'failed'
                })

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)


# Serve frontend static files
BACKEND_DIR = Path(__file__).parent.resolve()
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def root():
    """Serve the main HTML page."""
    return FileResponse(str(FRONTEND_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
