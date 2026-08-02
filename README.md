# Piny SDLC Agent Orchestrator

Un orquestador de agentes de IA diseñado para integrarse directamente en el ciclo de vida de desarrollo de software (SDLC) de proyectos de e-commerce.

Este sistema implementa dos capacidades fundamentales para acelerar el desarrollo:
1. **Automated Code Review Agent**: Un agente que revisa automáticamente los Pull Requests en busca de vulnerabilidades, deudas técnicas y asegura el cumplimiento de las reglas de negocio, comentando directamente línea por línea en GitHub.
2. **Agentic Knowledge Base (RAG)**: Un agente consultor que indexa el código fuente y las guías del proyecto para responder preguntas de arquitectura y negocio en tiempo real.

Este proyecto ha sido desarrollado como respuesta al Reto Técnico de PinApp. Para leer el racional detrás de las decisiones arquitectónicas, revisa el archivo [ARCHITECTURE_AND_DECISIONS.md](./ARCHITECTURE_AND_DECISIONS.md).

## Requisitos Previos
- Docker y Docker Compose
- Una cuenta de Google Cloud con permisos para usar Vertex AI (Gemini / Text Embeddings)
- Una GitHub App configurada e instalada en tu repositorio (para probar los PRs)

## Estructura del Proyecto
- `/app`: El código fuente del orquestador en FastAPI y la definición de los agentes de Langchain.
- `/example-ecommerce`: Un repositorio simulado de e-commerce sobre el cual operan los agentes (Código Base).

## Configuración y Ejecución

### 1. Variables de Entorno
Crea un archivo `.env` en la raíz de este proyecto con la siguiente estructura:

```env
# Credenciales GCP (Vertex AI)
GOOGLE_APPLICATION_CREDENTIALS=/app/gcp_credentials.json

# Autenticación GitHub App (Piny)
GITHUB_APP_ID=tu_app_id
GITHUB_APP_PRIVATE_KEY_PATH=/app/tu-llave.pem
```

*Importante: Asegúrate de colocar el archivo `gcp_credentials.json` y el archivo de tu llave privada `.pem` en la raíz de este repositorio. El `docker-compose` los montará automáticamente en la carpeta `/app` del contenedor.*

### 2. Levantar el Sistema
Una vez configurado el `.env`, simplemente corre:
```bash
docker-compose up --build
```
El orquestador estará escuchando peticiones en `http://localhost:8000`.

## ¿Cómo probarlo?

### Capacidad 1: Q&A de Reglas de Negocio
Con el servidor corriendo, puedes interrogar a la base de conocimiento usando el siguiente request (vía cURL o Postman):

```bash
curl -X POST http://localhost:8000/api/v1/orchestrate \
-H "Content-Type: application/json" \
-d '{
  "action_type": "qna",
  "payload": {
    "question": "¿Cuáles son las reglas de negocio de inventario y concurrencia para el checkout?"
  }
}'
```
El agente leerá el código y los markdowns dentro de `/example-ecommerce` y generará la respuesta.

### Capacidad 2: Code Review Automatizado
1. Expon tu puerto 8000 a internet (por ejemplo, usando `ngrok http 8000`).
2. Configura el Webhook URL en tu GitHub App para que apunte a `https://tu-url-ngrok.ngrok.app/webhook/github`.
3. Haz un cambio en el código dentro de la carpeta `/example-ecommerce` (por ejemplo, creando una validación defectuosa en `checkout.js`).
4. Sube los cambios y crea un Pull Request en tu repositorio asociado.
5. Observa cómo "Piny SDLC Agent" comienza su validación ("Pending") y al cabo de unos segundos deja sus comentarios inline y un reporte general ("Success" o "Failure").
