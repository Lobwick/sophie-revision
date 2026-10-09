FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY scripts/edn_mcp.py scripts/edn_kb.py scripts/edn_site.py scripts/edn_dash.py scripts/edn_exams.py scripts/edn_store.py scripts/edn_study.py scripts/
COPY scripts/static scripts/static
COPY agents agents
COPY skills skills
COPY knowledge/cours.db knowledge/cours.db
COPY data/cartes-edn.json data/planning-edn.json data/
ENV EDN_HOST=0.0.0.0 EDN_PORT=8001 EDN_DATA_DIR=/data EDN_COURS_DIR=/app/cours EDN_REQUIRE_PERSIST=1
# /data DOIT être un volume monté : le serveur refuse de démarrer sinon (EDN_REQUIRE_PERSIST). Le propriétaire du dossier monté peut
# différer de l'utilisateur du conteneur : git doit l'accepter (« dubious ownership »).
RUN mkdir /data && chown 1000 /data && git config --system --add safe.directory /data
USER 1000
CMD ["python3", "scripts/edn_mcp.py"]
