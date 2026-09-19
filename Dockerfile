FROM node:20-alpine

WORKDIR /app

# Dépendances du serveur d'abord (meilleure mise en cache des layers)
COPY server/package.json server/package-lock.json* ./server/
RUN cd server && npm install --omit=dev

# Puis le reste du site (pages statiques, css, js, données de référence)
COPY . .

ENV NODE_ENV=production
ENV PORT=8080
ENV DB_PATH=/app/db/store.json

EXPOSE 8080

CMD ["node", "server/server.js"]
