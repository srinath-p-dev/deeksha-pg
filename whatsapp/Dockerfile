FROM node:22-alpine
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY src ./src

# The WhatsApp login session lives in a Docker volume — treat it like a password
RUN mkdir -p /data/session && chown -R node:node /data/session
USER node

ENV HOST=0.0.0.0 \
    PORT=3001 \
    SESSION_DIR=/data/session

# Node 22.18+ runs TypeScript directly (type stripping)
CMD ["node", "src/index.ts"]
