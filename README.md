# PinApp SDLC AI Orchestrator

This repository contains the functional prototype for the **Multi-Agent SDLC Orchestrator**, developed for the PinApp technical challenge. 

It aims to solve common frictions in an e-commerce development team by providing two core AI capabilities:
1. **Code Review Agent:** Analyzes Pull Request diffs to detect security vulnerabilities, logic bugs, and suggest architecture improvements.
2. **Knowledge Agent (RAG):** Indexes a target repository and answers technical questions regarding the codebase to speed up onboarding and development.

## Tech Stack
* **Python 3.10**
* **FastAPI** (Orchestrator Router)
* **Google GenAI / Vertex AI** (Gemini 1.5 Pro & Flash)
* **LangChain & ChromaDB** (Vector Store for RAG)
* **Docker** (Operability)

## Prerequisites
To run this project, you need:
* Docker & Docker Compose installed.
* A Google Cloud account with Vertex AI enabled OR a Gemini API Key.

## Setup & Execution (3 Steps)

### 1. Clone the repository
```bash
git clone <tu-repositorio>
cd pinapp-sdlc-agents
```

### 2. Configure Credentials
Create a `.env` file in the root of the project with your Google API Key:
```bash
echo "GOOGLE_API_KEY=your_api_key_here" > .env
```
*(Alternatively, you can authenticate via `gcloud auth application-default login` if running locally without Docker).*

### 3. Run the System
```bash
docker-compose up --build
```
The FastAPI server will start at `http://localhost:8000`.

## Testing the Endpoints
You can test the Orchestrator via POST requests. We have provided two sample scenarios.

### Scenario 1: Q&A (Knowledge Agent)
```bash
curl -X POST "http://localhost:8000/api/v1/orchestrate" \
-H "Content-Type: application/json" \
-d '{
    "action_type": "qna",
    "payload": {
        "question": "¿Dónde y cómo se maneja la lógica del carrito de compras y qué vulnerabilidad tiene?"
    }
}'
```

### Scenario 2: Code Review (Reviewer Agent)
```bash
curl -X POST "http://localhost:8000/api/v1/orchestrate" \
-H "Content-Type: application/json" \
-d '{
    "action_type": "code_review",
    "payload": {
        "diff_content": "+ const total = req.body.total; \n+ // Trusting frontend total\n+ res.status(200).json({ success: true });"
    }
}'
```
