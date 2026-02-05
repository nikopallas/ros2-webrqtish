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
