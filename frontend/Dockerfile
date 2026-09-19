FROM node:20-alpine

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY package*.json ./
RUN npm install --fetch-retries=10 --fetch-retry-mintimeout=5000 --fetch-timeout=120000

# Rest of the source is bind-mounted over this in docker-compose.yml dev
# setup, but copy it too so the image is self-contained for other uses
# (e.g. `docker build` without compose).
COPY . .

EXPOSE 3000

# docker-compose.yml already runs `npm run dev` as the container command.
CMD ["npm", "run", "dev"]
