# Reto Técnico PinApp: Análisis y Propuesta de Solución

Este documento detalla el análisis del reto técnico y las decisiones arquitectónicas para el sistema multi-agente ("Piny SDLC Agent") que resuelve las fricciones del ciclo de desarrollo de e-commerce.

## 1. Capacidades Demostradas

Para abordar las fricciones del escenario ("revisar código toma tiempo" y "el conocimiento está disperso"), hemos construido un prototipo funcional que demuestra dos capacidades principales:

1.  **Revisar cambios de código y dar feedback (Code Review Agent):** Un agente que analiza diffs de Pull Requests (PRs) para detectar bugs, reglas de negocio no cumplidas y vulnerabilidades. Emite comentarios precisos "línea por línea" en GitHub y un resumen general.
2.  **Responder preguntas sobre el código o documentación (Knowledge/RAG Agent):** Un agente equipado con RAG (Retrieval-Augmented Generation) que indexa todo el repositorio e-commerce para responder dudas técnicas de arquitectura y negocio, acelerando el onboarding y resolución de dudas sin interrumpir a los seniors.

**¿Por qué estas dos?** Se complementan perfectamente en un flujo de CI/CD. Una actúa de forma reactiva (en el PR) reduciendo el tiempo de QA y Code Review, y la otra de forma proactiva (Q&A por API) reduciendo la dispersión del conocimiento.

---

## 2. Diseño Arquitectónico del Sistema

Construimos el sistema utilizando Python, Langchain y las APIs de Google Cloud (Vertex AI / Gemini).

### Componentes Principales:
1.  **Orquestador Ligero (FastAPI Router):** Actúa como el cerebro central. Recibe webhooks desde la GitHub App y los delega asíncronamente al agente correspondiente. También expone un endpoint `/api/v1/orchestrate` para consultas de Q&A en tiempo real.
2.  **Agentes Especializados:**
    *   **KnowledgeAgent:** Utiliza `ChromaDB` en memoria y embeddings de `Vertex AI` (`text-embedding-004`). Escanea el repositorio excluyendo carpetas irrelevantes (como `node_modules`), vectoriza el código/documentación y recupera el contexto para el LLM.
    *   **ReviewerAgent:** Utiliza el contexto provisto por el KnowledgeAgent + el diff del PR. Le pasa esta información a `gemini-1.5-pro` usando *Chain-of-Thought* para evaluar si el código cumple las reglas de negocio e identificar bugs, retornando un JSON estructurado.
3.  **Integración con GitHub App:** En lugar de usar Webhooks sueltos y un Personal Access Token (PAT), implementamos una verdadera "GitHub App" ("Piny SDLC Agent") que se autentica vía JWT. Esto permite comentar en los PRs con una identidad de bot oficial y agregar "Status Checks" formales que bloquean mergeos peligrosos.

---

## 3. Decisiones y Trade-offs (Balance de Condiciones)

### Costo vs Eficiencia (El límite de Vertex AI)
*   *Tensión:* Para tener contexto preciso de las reglas de negocio, necesitábamos indexar el código completo. Pero indexar miles de archivos con `text-embedding-004` es costoso y choca con los límites de la API (20.000 tokens por request).
*   *Decisión:* Implementamos un `os.walk` manual ultrarrápido que excluye físicamente la lectura de `node_modules` y `.next` antes de que Langchain los vea, reduciendo los archivos a leer de 5.000+ a ~40. Además, ajustamos el tamaño de los lotes (`batch_size=20`) para mantenernos en los límites gratuitos/bajos de Vertex AI sin crashear.
*   *Trade-off:* La indexación es más selectiva (solo extensiones clave: .js, .ts, .md), sacrificando la indexación de archivos estáticos o de configuración profunda en pos de velocidad y costo casi cero.

### Tiempo de Respuesta
*   *Tensión:* Un Code Review automatizado puede tardar. Si bloquea el Webhook de GitHub, GitHub asume que falló (timeout a los 10s).
*   *Decisión:* El orquestador usa `BackgroundTasks` de FastAPI. Al recibir un Webhook, responde un `200 OK` a GitHub en milisegundos y despacha el Code Review en un hilo secundario. Mientras tanto, notifica a GitHub App con un Status Check "Pending 🟡". Cuando termina, actualiza a "Success 🟢" o "Failure 🔴".

### Privacidad
*   *Decisión:* Optamos por Google Vertex AI porque sus políticas empresariales dictaminan explícitamente que los datos de la organización **no se usan para entrenar sus modelos fundacionales**. El código fuente está a salvo.
*   *Operabilidad de Secretos:* Toda la autenticación (GCP Credentials, GitHub App ID, Private Keys) se inyecta mediante un `.env` fuera del código fuente.

### Operabilidad
*   *Decisión:* Todo el ecosistema está encapsulado en un `docker-compose.yml` que monta el código del orquestador y el código del repositorio objetivo (`example-ecommerce`). Cualquier evaluador con Docker puede probarlo con solo 2 comandos.

---

## 4. Qué resolvimos con IA y qué con código determinístico

*   **IA:** 
    *   La lectura y entendimiento del *diff* (qué intentó hacer el desarrollador y en qué se equivocó).
    *   La recuperación semántica de las reglas de negocio en base al contexto del PR (Agentic RAG).
    *   La generación de la justificación técnica del comentario.
*   **Código Determinístico:** 
    *   La orquestación del Webhook y autenticación (JWT).
    *   El mapeo de líneas: parsear el JSON devuelto por la IA para mapear el problema con la línea *exacta* en el PR de GitHub y hacer el POST a la API de GitHub Comments.
    *   La exclusión de carpetas (`node_modules`) y el control del `batch_size` de embeddings.

---

## 5. Qué haríamos con más tiempo

1.  **Caché de Vector Store:** Actualmente la base ChromaDB corre en memoria inyectando todo el repositorio con cada PR para mantener la demo simple. En un caso real de alta concurrencia, guardaríamos ChromaDB en disco (Persist) y solo actualizaríamos los vectores de los archivos que hayan cambiado (detectado vía webhook `push`).
2.  **Agente de QA Automatizado:** Añadiríamos una capacidad que analice si el PR rompió algún test unitario (leyendo el log de Bitbucket Pipelines/GitHub Actions) e intente sugerir el fix automáticamente.
3.  **Métricas / LangSmith:** Conectaríamos la librería a LangSmith o Cloud Run Metrics para medir exactamente cuánto tiempo ahorran los devs gracias a los comentarios de la IA.
