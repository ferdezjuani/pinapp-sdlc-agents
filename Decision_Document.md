# Documento de Decisiones: SDLC AI Orchestrator

## 1. Capacidades Elegidas y Por Qué
Para abordar los problemas del equipo de e-commerce descritos en el reto (revisiones lentas, conocimiento disperso), elegí implementar las siguientes dos capacidades:

1. **Code Review Agent:** Revisa `diffs` de código buscando bugs lógicos, vulnerabilidades de seguridad y mejoras arquitectónicas. 
   - *Por qué:* Directamente ataca la fricción de "revisar código toma tiempo y es inconsistente". Estandariza la calidad del código antes de que un humano lo vea.
2. **Knowledge Agent (Q&A con RAG):** Responde preguntas técnicas sobre el código base leyendo el repositorio.
   - *Por qué:* Resuelve el problema de "arrancar una funcionalidad nueva es lento porque el conocimiento está disperso". Permite a los desarrolladores nuevos hacer *onboarding* rápido sin interrumpir a los seniors.

## 2. Diseño del Sistema
El sistema fue diseñado con un patrón de **Orquestador Ligero (Router)** usando FastAPI en Python.
- **Router (`/api/v1/orchestrate`):** Recibe un payload JSON y, basándose en la intención (`action_type`), enruta la petición al agente correspondiente. Esto permite escalar el sistema en el futuro (ej. añadiendo un agente de QA o de Deploy) sin acoplar la lógica.
- **Agentes como Clases Independientes:** Cada agente (`KnowledgeAgent` y `ReviewerAgent`) encapsula su propia lógica, su propio LLM y sus dependencias.

Para probar el sistema de manera predecible, evitamos hacer un fork de un proyecto gigantesco y optamos por generar un **pequeño código de ejemplo (`target-repo-ecommerce`)** con un carrito de compras y un endpoint de checkout. Esto nos dio control total para inyectar errores lógicos (ej. vulnerabilidad donde el frontend envía el total a cobrar) y demostrar el valor del Code Reviewer de forma determinista.

## 3. Manejo de Condiciones y Trade-offs

### Costo
* **Decisión:** Utilizamos una mezcla de modelos. Para el Code Review, que requiere alto razonamiento, usamos **Gemini 1.5 Pro**. Para el RAG (Q&A), como el contexto se inyecta mediante la base vectorial, usamos **Gemini 1.5 Flash**, que es significativamente más económico y rápido.
* **Trade-off:** Sacrificamos un nivel mínimo de razonamiento en respuestas casuales a cambio de mantener los costos a una fracción, ideal para consultas frecuentes durante el desarrollo.

### Tiempo de Respuesta
* **Decisión:** La indexación de documentos para el RAG se hace *offline* (o al inicializar el agente) y se almacena en ChromaDB.
* **Trade-off:** La primera vez que el sistema se levanta puede tardar un poco más en indexar el repositorio, pero a cambio garantizamos que las preguntas de los desarrolladores se respondan en ~2-5 segundos (tiempo de inferencia del LLM Flash), lo cual es razonable para un chat en tiempo real.

### Privacidad
* **Decisión:** Utilizamos variables de entorno (`.env`) en lugar de hardcodear llaves. Además, el diseño está pensado para conectarse a **Vertex AI** (GCP Enterprise), donde los datos del cliente no se usan para entrenar los modelos públicos de Google.
* **Trade-off:** Requiere que quien instale el sistema configure sus credenciales de Google Cloud localmente o inyecte la API Key de Gemini en el contenedor Docker.

### Operabilidad
* **Decisión:** Entregamos la solución 100% *Dockerizada* (`Dockerfile` y `docker-compose.yml`) con un `requirements.txt` limpio. 
* **Trade-off:** Añade una ligera sobrecarga a la imagen, pero asegura que el equipo evaluador de PinApp pueda correrlo en cualquier máquina (Mac, Windows, Linux) con un solo comando (`docker-compose up`).

## 4. Qué haría diferente con más tiempo
* **Integración con GitHub/Bitbucket:** En lugar de enviar payloads por cURL o Postman, crearía un Webhook real que escuche eventos de `pull_request` en GitHub y postee los comentarios del Code Review automáticamente en la interfaz.
* **Agente Evaluador (Capacidad 4):** Agregaría un tercer agente que lea el output del Reviewer y los resultados de un linter (ej. ESLint), y decida automáticamente si bloquea el PR o lo aprueba.
* **Bases de Datos Vectoriales en la Nube:** Migrar de ChromaDB local a un servicio administrado (ej. Vertex AI Vector Search o Pinecone) para que múltiples instancias del servidor FastAPI compartan el mismo índice.

## 5. Uso de IA en el desarrollo
Utilicé asistencia de IA para estructurar rápidamente el proyecto, escribir el boilerplate de FastAPI (modelos Pydantic) y redactar la configuración de Docker y docker-compose. Sin embargo, las decisiones arquitectónicas (como usar un Router Pattern, separar los modelos por agente para optimizar costos, y la técnica de Chain-of-Thought en el System Prompt) fueron producto de análisis propio basándome en mi experiencia como AI Engineer.
