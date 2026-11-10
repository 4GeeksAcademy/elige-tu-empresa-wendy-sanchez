#!/usr/bin/env python3
"""
Standalone RAG API server for HealthCore.

Launches only the RAG endpoints without requiring the full services/api
application (which has Python 3.14 / SQLModel compatibility issues).

Usage:
    QDRANT_URL=http://localhost:6333 uv run python3 services/api/routes/rag_standalone.py

Or via uvicorn directly:
    cd services/api && QDRANT_URL=http://localhost:6333 uv run uvicorn rag_standalone:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── Path setup ────────────────────────────────────────────────────
# The routes/ package lives under services/api/.
API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(API_DIR, "..", ".."))

for p in [PROJECT_ROOT, API_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── FastAPI app — must be defined BEFORE any @app decorator ────────
app = FastAPI(
    title="HealthCore RAG API",
    description="Retrieval-Augmented Generation for patient coordinators",
    version="0.2.0",
)

from fastapi.responses import HTMLResponse  # noqa: E402
from routes.knowledge import router as knowledge_router  # noqa: E402
from routes.rag import router as rag_router  # noqa: E402

# ── CORS — allow the Next.js frontend to call us ───────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static HTML UI (served at /) ──────────────────────────────────

HTML_UI = r"""<!DOCTYPE html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>HealthCore — Base de Conocimiento (RAG)</title>
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #e2e8f0; display: flex; min-height: 100vh; align-items: center; justify-content: center; }
      .card { background: #1e293b; border-radius: 1.5rem; padding: 2rem; max-width: 48rem; width: 100%; margin: 2rem; box-shadow: 0 25px 50px -12px rgba(0,0,0,.5); }
      h1 { font-size: 1.5rem; font-weight: 700; margin-bottom: .25rem; }
      .sub { color: #94a3b8; font-size: .875rem; margin-bottom: 1.5rem; }
      .samples { display: flex; flex-wrap: wrap; gap: .5rem; margin-bottom: 1rem; }
      .samples button { background: #334155; color: #e2e8f0; border: none; border-radius: .75rem; padding: .5rem .75rem; font-size: .75rem; cursor: pointer; transition: background .15s; }
      .samples button:hover { background: #475569; }
      .chat { max-height: 24rem; overflow-y: auto; margin-bottom: 1rem; display: flex; flex-direction: column; gap: .75rem; }
      .msg { padding: .75rem 1rem; border-radius: 1rem; max-width: 85%; line-height: 1.5; }
      .user { background: #3b82f6; color: #fff; align-self: flex-end; }
      .assistant { background: #334155; color: #e2e8f0; align-self: flex-start; }
      .error { background: #7f1d1d; color: #fca5a5; }
      .empty-state { text-align: center; padding: 3rem 1rem; color: #64748b; }
      .empty-state p { font-size: 1.125rem; margin-bottom: .5rem; }
      .empty-state small { font-size: .875rem; }
      .loading { display: flex; align-items: center; gap: .5rem; color: #94a3b8; }
      .spinner { width: 1.25rem; height: 1.25rem; border: 3px solid #3b82f6; border-top-color: transparent; border-radius: 9999px; animation: spin .6s linear infinite; }
      @keyframes spin { to { transform: rotate(360deg); } }
      .input-row { display: flex; gap: .5rem; }
      .input-row input { flex: 1; background: #0f172a; border: 1px solid #475569; border-radius: .75rem; padding: .75rem 1rem; color: #e2e8f0; font-size: .875rem; outline: none; }
      .input-row input:focus { border-color: #3b82f6; }
      .input-row button { background: #3b82f6; color: #fff; border: none; border-radius: .75rem; padding: .75rem 1.25rem; font-size: .875rem; cursor: pointer; }
      .input-row button:disabled { opacity: .5; cursor: not-allowed; }
    </style>
  </head>
  <body>
    <div class="card" id="app">
      <h1>🧠 Base de Conocimiento</h1>
      <p class="sub">Consulta las políticas de HealthCore — RAG + DeepSeek v4</p>
      <div class="samples">
        <button onclick="ask('¿Qué seguros aceptan en las clínicas de Estados Unidos?')">🏥 Seguros EE.UU.</button>
        <button onclick="ask('¿Cobran cargo por no-show a pacientes de Medicare?')">🛑 No-show Medicare</button>
        <button onclick="ask('¿Qué documentos necesito llevar a mi primera cita?')">📋 Documentos primera cita</button>
        <button onclick="ask('¿Cuánto tiempo tarda una referencia interna a un especialista?')">⏱ Referencia especialista</button>
      </div>
      <div class="chat" id="chat">
        <div class="empty-state">
          <p>💬 Haz una pregunta sobre las políticas de HealthCore</p>
          <small>Selecciona un ejemplo o escribe tu propia pregunta</small>
        </div>
      </div>
      <div class="loading" id="loading" style="display:none">
        <div class="spinner"></div>
        <span>Consultando la base de conocimiento...</span>
      </div>
      <div class="input-row">
        <input type="text" id="input" placeholder="Escribe tu pregunta aquí..." onkeydown="if(event.key==='Enter') send()" />
        <button id="sendBtn" onclick="send()">Enviar</button>
      </div>
    </div>
    <script>
      const API_BASE = window.location.origin;
      let loading = false;
      function addMsg(role, content, isError) {
        const chat = document.getElementById('chat');
        const empty = chat.querySelector('.empty-state');
        if (empty) empty.remove();
        const div = document.createElement('div');
        div.className = 'msg ' + role + (isError ? ' error' : '');
        div.textContent = content;
        chat.appendChild(div);
        chat.scrollTop = chat.scrollHeight;
      }
      async function ask(q) {
        if (!q || loading) return;
        loading = true;
        document.getElementById('loading').style.display = 'flex';
        document.getElementById('sendBtn').disabled = true;
        addMsg('user', q);
        try {
          const resp = await fetch(API_BASE + '/knowledge/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: q })
          });
          if (!resp.ok) throw new Error('HTTP ' + resp.status);
          const data = await resp.json();
          addMsg('assistant', data.answer);
        } catch (e) {
          addMsg('assistant', '⚠️ Error: no pude conectar con la base de conocimiento. ¿Estará el servidor funcionando?', true);
        } finally {
          loading = false;
          document.getElementById('loading').style.display = 'none';
          document.getElementById('sendBtn').disabled = false;
        }
      }
      function send() {
        const input = document.getElementById('input');
        const q = input.value.trim();
        if (!q) return;
        input.value = '';
        ask(q);
      }
    </script>
  </body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return HTML_UI


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "rag-standalone", "version": "0.2.0"}


app.include_router(knowledge_router)
app.include_router(rag_router)

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("RAG_HOST", "0.0.0.0")
    port = int(os.getenv("RAG_PORT", "8000"))
    logger.info("Starting RAG standalone server on %s:%s", host, port)
    uvicorn.run("rag_standalone:app", host=host, port=port, reload=False)