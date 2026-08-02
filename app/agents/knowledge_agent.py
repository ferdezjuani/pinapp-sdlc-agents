import os
import shutil
from typing import List
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_vertexai import VertexAIEmbeddings, VertexAI
from langchain_chroma import Chroma
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

class KnowledgeAgent:
    def __init__(self, repo_path: str, persist_directory: str = None):
        self.repo_path = repo_path
        self.persist_directory = persist_directory
        
        # We assume GOOGLE_APPLICATION_CREDENTIALS or gcloud auth is configured
        self.embeddings = VertexAIEmbeddings(model_name="text-embedding-004")
        self.llm = VertexAI(model_name="gemini-2.5-flash")
        
        self.vector_store = None
        
        # Try to load existing vector store, otherwise it stays None until index_repo is called
        if self.persist_directory and os.path.exists(self.persist_directory):
            self.vector_store = Chroma(
                persist_directory=self.persist_directory, 
                embedding_function=self.embeddings
            )

    def index_repo(self):
        """Loads all JS/TS/MD files from the target repo, chunks them, and stores in ChromaDB."""
        print(f"Indexing repository at {self.repo_path}...", flush=True)
        
        # Wipe previous ChromaDB to avoid stale context if using persistence
        if self.persist_directory and os.path.exists(self.persist_directory):
            shutil.rmtree(self.persist_directory, ignore_errors=True)
            self.vector_store = None
        
        # Load multiple file extensions, explicitly ignoring node_modules
        docs = []
        for root, dirs, files in os.walk(self.repo_path):
            # Modifying dirs in-place to skip scanning these directories
            if 'node_modules' in dirs:
                dirs.remove('node_modules')
            if '.next' in dirs:
                dirs.remove('.next')
            if '.git' in dirs:
                dirs.remove('.git')
                
            for file in files:
                if file.endswith((".js", ".ts", ".md")):
                    file_path = os.path.join(root, file)
                    try:
                        loader = TextLoader(file_path)
                        docs.extend(loader.load())
                    except Exception as e:
                        pass # Ignore loading errors silently to keep logs clean
        
        print(f"Total documents loaded: {len(docs)}", flush=True)
        
        # Split text into chunks
        print("Splitting documents...", flush=True)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        splits = text_splitter.split_documents(docs)
        print(f"Total splits created: {len(splits)}", flush=True)
        
        # Create Vector Store (In-memory if persist_directory is None)
        self.vector_store = Chroma(
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )
        
        # Add documents in batches to avoid Vertex AI 20000 tokens per request limit
        batch_size = 20
        print("Adding documents to ChromaDB...", flush=True)
        for i in range(0, len(splits), batch_size):
            print(f"Adding batch {i//batch_size + 1}/{(len(splits)-1)//batch_size + 1}...", flush=True)
            batch = splits[i:i+batch_size]
            self.vector_store.add_documents(batch)
            
        print(f"Indexed {len(splits)} chunks successfully in batches of {batch_size}.", flush=True)

    def answer_question(self, question: str) -> str:
        """Retrieves relevant context and answers the question using Gemini."""
        if not self.vector_store:
            return "Error: Vector store is not initialized. Please index the repo first."
            
        retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
        
        system_prompt = (
            "You are an expert AI software engineer assistant helping a developer understand their codebase. "
            "Use the following pieces of retrieved context to answer the question. "
            "If you don't know the answer, say that you don't know based on the context. "
            "Context: {context}"
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        
        question_answer_chain = create_stuff_documents_chain(self.llm, prompt)
        rag_chain = create_retrieval_chain(retriever, question_answer_chain)
        
        response = rag_chain.invoke({"input": question})
        return response["answer"]
