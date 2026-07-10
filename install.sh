#!/bin/bash
set -e

echo "🚀 Installing Markly..."

# 1. Detect OS & Dependencies
OS="$(uname -s)"
ARCH="$(uname -m)"
echo "Detected: $OS ($ARCH)"

if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed. Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "❌ Error: Docker Compose v2 is required. Please install or enable docker-compose."
    exit 1
fi

# 2. Set up Directories
INSTALL_DIR="$HOME/.markly"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

echo "📥 Setting up Docker Compose configuration at $INSTALL_DIR..."

# In production, this would fetch from Github, but here we write/copy the docker-compose.yml
# For local installation simulation, we copy it from the current repo if present, or write it directly
cat << 'EOF' > docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: markly_postgres
    environment:
      POSTGRES_USER: markly
      POSTGRES_PASSWORD: markly
      POSTGRES_DB: markly_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U markly -d markly_dev"]
      interval: 5s
      timeout: 5s
      retries: 5

  chroma:
    image: chromadb/chroma:latest
    container_name: markly_chroma
    ports:
      - "8000:8000"
    volumes:
      - chroma_data:/chroma/chroma
    restart: unless-stopped

  markly-cli:
    image: markly-cli:latest
    container_name: markly_cli
    stdin_open: true
    tty: true
    volumes:
      - .:/app
      - /var/run/docker.sock:/var/run/docker.sock
      - secrets_data:/root/.markly
      - skills_data:/app/markly/memory/skills
    environment:
      - DATABASE_URL=postgresql://markly:markly@postgres:5432/markly_dev
    depends_on:
      postgres:
        condition: service_healthy
      chroma:
        condition: service_started

volumes:
  postgres_data:
  chroma_data:
  secrets_data:
  skills_data:
EOF

# 3. Pull/Build container
echo "🏗️ Building/Pulling Markly container..."
docker compose pull || true

# 4. Install host wrapper script
WRAPPER_PATH="/usr/local/bin/markly"
LOCAL_BIN="$HOME/.local/bin"

USE_SUDO=false
if [ -w "/usr/local/bin" ]; then
    DEST_PATH="/usr/local/bin/markly"
else
    echo "⚠️ /usr/local/bin is not writable without sudo."
    mkdir -p "$LOCAL_BIN"
    if [[ ":$PATH:" == *":$LOCAL_BIN:"* ]]; then
        DEST_PATH="$LOCAL_BIN/markly"
        echo "Installing to $DEST_PATH"
    else
        DEST_PATH="/usr/local/bin/markly"
        USE_SUDO=true
        echo "Will require sudo to write to $DEST_PATH"
    fi
fi

WRITE_CMD="cat << 'EOF' > $DEST_PATH
#!/bin/bash
docker compose -f $INSTALL_DIR/docker-compose.yml run --rm -it markly-cli \"\$@\"
EOF
chmod +x $DEST_PATH"

if [ "$USE_SUDO" = true ]; then
    sudo bash -c "$WRITE_CMD"
else
    bash -c "$WRITE_CMD"
fi

echo "✅ Markly successfully installed!"
echo ""
echo "👉 Next steps:"
echo "   1. Run 'markly setup' to configure your API keys."
echo "   2. Start creating with 'markly run \"Your goal here\"'"
echo ""
