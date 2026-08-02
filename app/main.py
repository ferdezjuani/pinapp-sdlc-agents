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
        agent = KnowledgeAgent(repo_path="/target-repo-ecommerce")
        
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
        pr_number = pr["number"]
        installation_id = payload.get("installation", {}).get("id")
        
        print(f"PROCESANDO PR: url={pr_api_url} repo={repo_full_name} sha={head_sha}", flush=True)
        
        # Procesamos en background para no bloquear el Webhook de GitHub (tiene timeout corto)
        background_tasks.add_task(process_github_pr, pr_api_url, comments_url, repo_full_name, head_sha, pr_number, installation_id)
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
        "context": "Security & Architecture Review"
    }
    requests.post(url, headers=headers, json=data)

def get_github_installation_token(app_id: str, private_key_path: str, installation_id: int) -> str:
    import time
    import jwt
    import requests
    
    try:
        with open(private_key_path, 'r') as f:
            private_key = f.read()
            
        payload = {
            'iat': int(time.time()),
            'exp': int(time.time()) + (10 * 60),
            'iss': app_id
        }
        
        encoded_jwt = jwt.encode(payload, private_key, algorithm='RS256')
        
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {encoded_jwt}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.post(url, headers=headers)
        if response.status_code == 201:
            return response.json().get("token")
        else:
            print(f"Failed to get installation token: {response.text}", flush=True)
            return None
    except Exception as e:
        print(f"Error generating JWT: {e}", flush=True)
        return None

def process_github_pr(pr_api_url: str, comments_url: str, repo_full_name: str, head_sha: str, pr_number: int, installation_id: int):
    import requests
    from app.agents.reviewer_agent import ReviewerAgent
    import json
    from dotenv import load_dotenv
    
    # Forzamos la carga del .env montado en el contenedor
    load_dotenv()
    
    app_id = os.environ.get("GITHUB_APP_ID")
    private_key_path = os.environ.get("GITHUB_APP_PRIVATE_KEY_PATH")
    
    print(f"[DEBUG] app_id={app_id}, private_key_path={private_key_path}, installation_id={installation_id}", flush=True)
    
    if app_id and private_key_path and installation_id:
        print("Autenticando como GitHub App...", flush=True)
        token = get_github_installation_token(app_id, private_key_path, installation_id)
    else:
        print("Autenticando con GITHUB_TOKEN clásico...", flush=True)
        token = os.environ.get("GITHUB_TOKEN")
        
    if not token:
        print("ERROR: No se pudo obtener un token de autenticación (Ni de App ni PAT)", flush=True)
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
    
    # 3. Procesar problemas e intentar publicar comentarios inline
    issues = review.get("issues", [])
    general_issues = []
    
    if issues:
        print(f"Procesando {len(issues)} issues encontrados por Gemini...", flush=True)
        for issue in issues:
            file_path = issue.get("file_path")
            line_number = issue.get("line_number")
            desc = issue.get("description")
            
            if file_path and line_number:
                review_url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/comments"
                inline_payload = {
                    "body": f"🤖 **Gemini AI:** {desc}",
                    "commit_id": head_sha,
                    "path": file_path,
                    "line": int(line_number)
                }
                res = requests.post(review_url, headers=headers, json=inline_payload)
                if res.status_code == 201:
                    print(f"Comentario inline publicado en {file_path}:{line_number}", flush=True)
                else:
                    print(f"Fallo al publicar comentario inline (Probablemente línea no modificada en PR): {res.status_code}", flush=True)
                    general_issues.append(issue)
            else:
                general_issues.append(issue)

    # 4. Formatear el comentario general de Markdown
    comment_body = f"## 🤖 Gemini AI Code Review\n\n"
    
    risk_level = review.get('risk_level', 'UNKNOWN').upper()
    risk_emoji = "🔴" if risk_level == "HIGH" else "🟡" if risk_level == "MEDIUM" else "🟢"
    comment_body += f"**Nivel de Riesgo:** {risk_emoji} {risk_level}\n\n"
    
    comment_body += f"### Análisis\n{review.get('analysis', '')}\n\n"
    
    if general_issues:
        comment_body += "### 🚨 Problemas Adicionales\n"
        for issue in general_issues:
            file_str = f"`{issue.get('file_path')}` " if issue.get('file_path') else ""
            line_str = f"Línea {issue.get('line_number', '?')}"
            comment_body += f"- **{file_str}{line_str}**: {issue.get('description', '')}\n"
    elif not issues:
        comment_body += "### ✨ Todo se ve excelente\nNo se detectaron problemas de seguridad o lógica.\n"
        
    # 5. Postear comentario general en GitHub
    print(f"Posteando comentario general en {comments_url}...", flush=True)
    post_res = requests.post(comments_url, headers=headers, json={"body": comment_body})
    
    if post_res.status_code == 201:
        print("¡Comentario general posteado exitosamente!", flush=True)
    else:
        print(f"Error al postear comentario general: {post_res.status_code} - {post_res.text}", flush=True)
        
    # Reportamos el estado final a GitHub
    if risk_level == "HIGH":
        set_commit_status(repo_full_name, head_sha, "failure", "Se detectaron vulnerabilidades críticas.", token)
    else:
        set_commit_status(repo_full_name, head_sha, "success", "Revisión superada.", token)
