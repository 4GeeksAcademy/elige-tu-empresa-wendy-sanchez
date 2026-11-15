"""Agente LangGraph de soporte — HealthCore Knowledge Base.

Este paquete contiene el grafo de LangGraph que implementa el flujo
de razonamiento del agente de soporte: recibe una pregunta, recupera
contexto de la base de conocimiento RAG, y genera una respuesta trazable.

Nodos con una sola responsabilidad. Aristas condicionales explícitas.
Trazabilidad completa mediante checkpointing en cada transición.
"""