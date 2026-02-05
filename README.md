# ROS2 Web GUI

A lightweight web-based alternative to rqt for ROS2, featuring topic monitoring/publishing and interactive node graph visualization.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![ROS2](https://img.shields.io/badge/ROS2-Jazzy-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## Features

- **Topic Panel**: List, search, subscribe to, and publish ROS2 topics in real-time
- **Node Graph**: Interactive D3.js force-directed graph showing nodes, topics, and connections
- **Real-time Updates**: WebSocket-based message streaming with live message rate display
- **Dark Theme**: Modern, eye-friendly interface
- **No Dependencies on rqt/Qt**: Pure web-based solution accessible from any browser

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Web Browser                          │
│  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │  Topic Panel    │  │      Node Graph (D3.js)     │  │
│  │  - List/Filter  │  │      - Interactive SVG      │  │
│  │  - Subscribe    │  │      - Pan/Zoom             │  │
│  │  - Publish      │  │      - Click to inspect     │  │
│  └─────────────────┘  └─────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────┘
                           │ WebSocket + REST
┌──────────────────────────┴──────────────────────────────┐
│              FastAPI Backend (Python)                   │
│  ┌─────────────────────────────────────────────────┐   │
│  │                   rclpy Node                     │   │
│  │  - Topic discovery & subscription               │   │
│  │  - Node/graph introspection                     │   │
│  │  - Message publishing                           │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                           │
                      ROS2 Network
```

## Requirements

- Ubuntu 24.04 (or compatible Linux distribution)
- ROS2 Jazzy
- Python 3.10+
- Modern web browser (Chrome, Firefox, Edge, Safari)

## Installation on Ubuntu 24.04

### 1. Install ROS2 Jazzy (if not already installed)

Follow the [official ROS2 Jazzy installation guide](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html) or use these commands:

```bash
# Set locale
sudo apt update && sudo apt install locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# Add ROS2 repository
sudo apt install software-properties-common
sudo add-apt-repository universe
sudo apt update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Install ROS2 Jazzy
sudo apt update
sudo apt install ros-jazzy-desktop
```

### 2. Clone and Install ROS2 Web GUI

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/ros2-web-gui.git
cd ros2-web-gui

# Install Python dependencies
pip install -r backend/requirements.txt
```

## Usage

### Quick Start

```bash
# Terminal 1: Start the web GUI
source /opt/ros/jazzy/setup.bash
cd ros2-web-gui/backend
python main.py
```

Open your browser to **http://localhost:8000**

### Testing with Demo Nodes

```bash
# Terminal 2: Run a test publisher
source /opt/ros/jazzy/setup.bash
ros2 run demo_nodes_cpp talker
```

You should see the `/chatter` topic appear in the web interface.

### Running as a Service (Optional)

Create a systemd service for auto-start:

```bash
sudo nano /etc/systemd/system/ros2-web-gui.service
```

```ini
[Unit]
Description=ROS2 Web GUI
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
Environment="PATH=/opt/ros/jazzy/bin:/usr/local/bin:/usr/bin"
ExecStart=/bin/bash -c 'source /opt/ros/jazzy/setup.bash && cd /path/to/ros2-web-gui/backend && python main.py'
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable ros2-web-gui
sudo systemctl start ros2-web-gui
```

## Docker Deployment

### Option 1: Standalone Container

```bash
# Build the image
docker build -t ros2-web-gui .

# Run with host network (for ROS2 discovery)
docker run -it --rm --network host ros2-web-gui
```

### Option 2: With Existing ROS2 Container

If you already have ROS2 running in a container:

```bash
# Run sharing the network with your ROS2 container
docker run -it --rm \
  --network container:YOUR_ROS2_CONTAINER \
  -p 8000:8000 \
  ros2-web-gui
```

### Dockerfile

Create a `Dockerfile` in the project root:

```dockerfile
FROM ros:jazzy

WORKDIR /app

# Install Python dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip3 install --break-system-packages -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["bash", "-c", "source /opt/ros/jazzy/setup.bash && python3 backend/main.py"]
```

## API Reference

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/topics` | List all topics with message types |
| GET | `/api/topics/{topic}/type` | Get message type definition |
| POST | `/api/topics/{topic}/publish` | Publish a message to a topic |
| GET | `/api/nodes` | List all nodes |
| GET | `/api/graph` | Get node graph data for visualization |

### WebSocket

Connect to `/ws/topics` for real-time topic subscriptions.

**Subscribe to a topic:**
```json
{"action": "subscribe", "topic": "/chatter"}
```

**Unsubscribe:**
```json
{"action": "unsubscribe", "topic": "/chatter"}
```

**Received messages:**
```json
{"type": "message", "topic": "/chatter", "data": {"data": "Hello World"}}
```

## Project Structure

```
ros2-web-gui/
├── backend/
│   ├── main.py           # FastAPI app, REST & WebSocket handlers
│   ├── ros_bridge.py     # rclpy node wrapper, ROS2 interface
│   ├── message_utils.py  # ROS msg <-> JSON conversion
│   └── requirements.txt  # Python dependencies
├── frontend/
│   ├── index.html        # Main HTML page
│   ├── style.css         # Dark theme styling
│   ├── app.js            # WebSocket client & REST API utilities
│   ├── topics.js         # Topic panel functionality
│   └── graph.js          # D3.js graph visualization
├── .gitignore
├── LICENSE
└── README.md
```

## Troubleshooting

### Topics not appearing

1. Make sure ROS2 is sourced before starting the backend:
   ```bash
   source /opt/ros/jazzy/setup.bash
   ```

2. Check that your ROS2 nodes are running and publishing:
   ```bash
   ros2 topic list
   ```

3. Verify network connectivity (especially in Docker/multi-machine setups)

### WebSocket connection fails

- Check that port 8000 is not blocked by a firewall
- Ensure the backend is running without errors

### Permission issues

If you see permission errors when installing Python packages:
```bash
pip install --user -r backend/requirements.txt
```

Or use a virtual environment:
```bash
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### Docker networking issues

- Use `--network host` for automatic ROS2 discovery
- If using Docker on macOS, note that `--network host` doesn't expose ports - use `-p 8000:8000` instead

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Graph visualization powered by [D3.js](https://d3js.org/)
- Designed as a lightweight alternative to [rqt](http://wiki.ros.org/rqt)
