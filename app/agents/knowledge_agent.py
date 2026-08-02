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
        print(f"Indexing repository at {self.repo_path}...")
        
        # Wipe previous ChromaDB to avoid stale context if using persistence
        if self.persist_directory and os.path.exists(self.persist_directory):
            shutil.rmtree(self.persist_directory, ignore_errors=True)
            self.vector_store = None
        
        # Load multiple file extensions
        docs = []
        for ext in ["**/*.js", "**/*.ts", "**/*.md"]:
            loader = DirectoryLoader(
                self.repo_path, 
                glob=ext, 
                loader_cls=TextLoader,
                show_progress=False
            )
            try:
                docs.extend(loader.load())
            except Exception as e:
                print(f"Skipping {ext}: {e}")
        
        # Split text into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        splits = text_splitter.split_documents(docs)
        
        # Create Vector Store (In-memory if persist_directory is None)
        self.vector_store = Chroma.from_documents(
            documents=splits, 
            embedding=self.embeddings, 
            persist_directory=self.persist_directory
        )
        print(f"Indexed {len(splits)} chunks successfully.")

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
