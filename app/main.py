from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

app = FastAPI(title="PinApp SDLC Orchestrator", version="1.0.0")

# Request Models
class OrchestratorRequest(BaseModel):
    action_type: str # "code_review" or "qna"
    payload: Dict[str, Any]

# Pydantic schemas for specific payloads
class CodeReviewPayload(BaseModel):
    diff_content: str
    pr_url: Optional[str] = None

class QnAPayload(BaseModel):
    question: str
    context_filters: Optional[Dict[str, str]] = None

@app.get("/")
def health_check():
    return {"status": "ok", "message": "PinApp SDLC Orchestrator is running"}

@app.post("/api/v1/orchestrate")
async def orchestrate(request: OrchestratorRequest):
    """
    Main router endpoint that delegates tasks to specialized agents based on action_type.
    """
    if request.action_type == "code_review":
        from app.agents.reviewer_agent import ReviewerAgent
        import requests
        
        agent = ReviewerAgent()
        
        diff = request.payload.get("diff_content", "")
        pr_url = request.payload.get("pr_url", "")
        
        if not diff and pr_url:
            # Si nos pasan un enlace de PR de GitHub, podemos extraer el diff agregando .diff al final
            diff_url = pr_url if pr_url.endswith(".diff") else f"{pr_url}.diff"
            try:
                response = requests.get(diff_url)
                if response.status_code == 200:
                    diff = response.text
                else:
                    raise HTTPException(status_code=400, detail=f"No se pudo descargar el diff del PR. Status: {response.status_code}")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error al conectar con la URL del PR: {str(e)}")

        if not diff:
            raise HTTPException(status_code=400, detail="Debes enviar 'diff_content' o un 'pr_url' público de GitHub")
            
        review_result = agent.review_code(diff)
        return {"status": "success", "agent": "ReviewerAgent", "review": review_result}
        
    elif request.action_type == "qna":
        from app.agents.knowledge_agent import KnowledgeAgent
        # Assuming the target repo is parallel to this project folder
        agent = KnowledgeAgent(repo_path="../target-repo-ecommerce")
        
        # If vector store is not initialized, try to index it (for prototype simplicity)
        if agent.vector_store is None:
            agent.index_repo()
            
        answer = agent.answer_question(request.payload.get("question", ""))
        return {"status": "success", "agent": "KnowledgeAgent", "answer": answer}
        
    else:
        raise HTTPException(status_code=400, detail="Invalid action_type. Use 'code_review' or 'qna'.")

from fastapi import Request, BackgroundTasks
import os

@app.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint para recibir Webhooks de GitHub cuando se crea o actualiza un PR.
    """
    payload = await request.json()
    action = payload.get("action", "unknown action")
    print(f"RECIBIDO WEBHOOK: action={action}", flush=True)
    
    # Solo procesamos si el evento es sobre un Pull Request (abierto, reabierto o actualizado)
    if "pull_request" in payload and action in ["opened", "synchronize", "reopened"]:
        pr = payload["pull_request"]
        # Usamos la URL base de la API del PR para obtener el Diff (más seguro con tokens)
        pr_api_url = pr["url"]
        comments_url = pr["comments_url"]
        
        # Extraer variables para el status check
        repo_full_name = payload["repository"]["full_name"]
        head_sha = pr["head"]["sha"]
        
        print(f"PROCESANDO PR: url={pr_api_url} repo={repo_full_name} sha={head_sha}", flush=True)
        
        # Procesamos en background para no bloquear el Webhook de GitHub (tiene timeout corto)
        background_tasks.add_task(process_github_pr, pr_api_url, comments_url, repo_full_name, head_sha)
        return {"status": "processing", "message": "PR review triggered in background"}
        
    print(f"IGNORANDO WEBHOOK. payload_keys={list(payload.keys())}", flush=True)
    return {"status": "ignored", "message": "Event is not a PR opened/synchronize"}

def set_commit_status(repo_full_name: str, sha: str, state: str, description: str, token: str):
    """
    Actualiza el estado (check) del commit en GitHub.
    States validos: 'pending', 'success', 'error', 'failure'
    """
    import requests
    url = f"https://api.github.com/repos/{repo_full_name}/statuses/{sha}"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "state": state,
        "description": description[:140], # Max 140 chars
        "context": "Gemini SDLC Agent"
    }
    requests.post(url, headers=headers, json=data)

def process_github_pr(pr_api_url: str, comments_url: str, repo_full_name: str, head_sha: str):
    import requests
    from app.agents.reviewer_agent import ReviewerAgent
    import json
    from dotenv import load_dotenv
    
    # Forzamos la carga del .env montado en el contenedor
    load_dotenv()
    
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN no está configurado en .env", flush=True)
        return
        
    headers = {
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    # Reportamos estado PENDING (amarillo)
    set_commit_status(repo_full_name, head_sha, "pending", "La IA está analizando tu código...", token)
    
    # 1. Obtener el Diff del PR usando el header Accept de diff
    diff_headers = headers.copy()
    diff_headers["Accept"] = "application/vnd.github.v3.diff"
    
    print(f"Descargando diff de {pr_api_url}...", flush=True)
    response = requests.get(pr_api_url, headers=diff_headers)
    
    if response.status_code != 200:
        print(f"Error descargando el diff: {response.status_code} - {response.text}", flush=True)
        set_commit_status(repo_full_name, head_sha, "error", "Error descargando el código.", token)
        return
        
    diff_content = response.text
    if not diff_content.strip():
        print("El diff está vacío.", flush=True)
        set_commit_status(repo_full_name, head_sha, "success", "No hay cambios de código para revisar.", token)
        return
        
    # 2. Obtener Contexto de Negocio (Agentic RAG)
    from app.agents.knowledge_agent import KnowledgeAgent
    print("Iniciando indexación de reglas de negocio...", flush=True)
    knowledge_agent = KnowledgeAgent(repo_path="/target-repo-ecommerce")
    knowledge_agent.index_repo()
    
    query = f"Busca cualquier regla de negocio, contrato o guía de arquitectura en el repositorio que se relacione con el siguiente diff de código:\n\n{diff_content}"
    print("Consultando al KnowledgeAgent...", flush=True)
    business_context = knowledge_agent.answer_question(query)
    
    # 3. Correr el agente revisor
    print("Iniciando Code Review con Gemini...", flush=True)
    agent = ReviewerAgent()
    review = agent.review_code(diff_content, business_context)
    
    # 3. Formatear la respuesta como comentario de Markdown
    comment_body = f"## 🤖 Gemini AI Code Review\n\n"
    
    risk_level = review.get('risk_level', 'UNKNOWN').upper()
    risk_emoji = "🔴" if risk_level == "HIGH" else "🟡" if risk_level == "MEDIUM" else "🟢"
    comment_body += f"**Nivel de Riesgo:** {risk_emoji} {risk_level}\n\n"
    
    comment_body += f"### Análisis\n{review.get('analysis', '')}\n\n"
    
    issues = review.get("issues", [])
    if issues:
        comment_body += "### 🚨 Problemas Detectados\n"
        for issue in issues:
            comment_body += f"- **Línea {issue.get('line_number', '?')}**: {issue.get('description', '')}\n"
    else:
        comment_body += "### ✨ Todo se ve excelente\nNo se detectaron problemas de seguridad o lógica.\n"
        
    # 4. Postear comentario en GitHub
    print(f"Posteando comentario en {comments_url}...", flush=True)
    post_res = requests.post(comments_url, headers=headers, json={"body": comment_body})
    
    if post_res.status_code == 201:
        print("¡Comentario posteado exitosamente!", flush=True)
    else:
        print(f"Error al postear comentario: {post_res.status_code} - {post_res.text}", flush=True)
        
    # Reportamos el estado final a GitHub
    if risk_level == "HIGH":
        set_commit_status(repo_full_name, head_sha, "failure", "Se detectaron vulnerabilidades críticas.", token)
    else:
        set_commit_status(repo_full_name, head_sha, "success", "Revisión superada.", token)
