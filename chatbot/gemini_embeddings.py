import os
import google.generativeai as genai
from langchain_core.embeddings import Embeddings
import logging
import time
from typing import List, Optional
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class GeminiEmbeddings(Embeddings):
    """Enhanced Gemini embeddings with error handling and retry logic."""
    
    def __init__(self, 
                 model_name: str = "models/embedding-001", 
                 task_type: str = "retrieval_document",
                 max_retries: int = 3,
                 retry_delay: float = 1.0):
        """
        Initialize Gemini embeddings with enhanced configuration.
        
        Args:
            model_name: The Gemini embedding model to use
            task_type: Task type for embeddings (retrieval_document, retrieval_query, etc.)
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries (exponential backoff)
        """
        self.model_name = model_name
        self.task_type = task_type
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        if "GEMINI_API_KEY" not in os.environ:
            raise ValueError("Gemini API key not found in environment variables.")
        
        try:
            genai.configure(api_key=os.environ["GEMINI_API_KEY"])
            logger.info(f"Gemini API configured with model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to configure Gemini API: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    def _embed_text(self, text: str, task_type: Optional[str] = None) -> List[float]:
        """
        Embed a single text with retry logic.
        
        Args:
            text: Text to embed
            task_type: Override task type if needed
            
        Returns:
            List of embedding values
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return [0.0] * 768  # Return zero vector for empty text
        
        try:
            # Truncate text if too long (Gemini has limits)
            if len(text) > 20000:
                text = text[:20000]
                logger.warning("Text truncated to 20000 characters for embedding")
            
            response = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type=task_type or self.task_type,
            )
            
            embedding = response["embedding"]
            
            if not embedding:
                logger.error("Received empty embedding from Gemini API")
                raise ValueError("Empty embedding received")
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            logger.error(f"Text preview: {text[:100]}...")
            raise
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple documents with batch processing and error handling.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings
        """
        if not texts:
            logger.warning("Empty texts list provided for embedding")
            return []
        
        embeddings = []
        failed_indices = []
        
        for i, text in enumerate(texts):
            try:
                embedding = self._embed_text(text, "retrieval_document")
                embeddings.append(embedding)
                
                # Add small delay to avoid rate limiting
                if i > 0 and i % 10 == 0:
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Failed to embed document {i}: {e}")
                failed_indices.append(i)
                # Use zero vector as fallback
                embeddings.append([0.0] * 768)
        
        if failed_indices:
            logger.warning(f"Failed to embed documents at indices: {failed_indices}")
        
        logger.info(f"Successfully embedded {len(embeddings)} documents")
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """
        Embed a query text.
        
        Args:
            text: Query text to embed
            
        Returns:
            Query embedding
        """
        try:
            embedding = self._embed_text(text, "retrieval_query")
            logger.debug(f"Query embedded successfully: {text[:50]}...")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            logger.error(f"Query: {text}")
            raise
    
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Async version of embed_documents (fallback to sync for now).
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings
        """
        # For now, run sync version in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed_documents, texts)
    
    async def aembed_query(self, text: str) -> List[float]:
        """
        Async version of embed_query (fallback to sync for now).
        
        Args:
            text: Query text to embed
            
        Returns:
            Query embedding
        """
        # For now, run sync version in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed_query, text)
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings from this model."""
        return 768  # Gemini embedding dimension
    
    def health_check(self) -> bool:
        """Check if the embedding service is healthy."""
        try:
            test_embedding = self._embed_text("Health check test")
            return len(test_embedding) > 0
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False