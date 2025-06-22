"""
Enterprise Vector Store Service for IntelliBrowse MCP Server

This service provides comprehensive vector storage and retrieval capabilities
for DOM elements and Gherkin steps using ChromaDB with enterprise-grade
security, audit logging, and performance optimization.

Features:
- Singleton pattern with async thread-safe initialization
- Dual collections for DOM elements and Gherkin steps
- Configuration-driven setup with environment variables
- Comprehensive audit logging for compliance
- Batch operations for performance
- Metadata-rich storage with advanced filtering
- Automatic error recovery and database healing
- RBAC-ready with security context propagation
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.utils import embedding_functions
from loguru import logger
from pydantic import BaseModel, Field, validator

try:
    from config.settings import settings
except ImportError:
    # Fallback for when running directly from mcp directory
    from config.settings import settings
try:
    from core.exceptions import VectorStoreError, VectorStoreConnectionError
except ImportError:
    # Fallback for when running directly from mcp directory
    from core.exceptions import VectorStoreError, VectorStoreConnectionError
try:
    from schemas.vector_store_schemas import (
        DOMElementData,
        GherkinStepData,
        VectorSearchRequest,
        VectorSearchResponse,
        VectorStoreMetrics,
        ElementAnalysisData
    )
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.vector_store_schemas import (
        DOMElementData,
        GherkinStepData,
        VectorSearchRequest,
        VectorSearchResponse,
        VectorStoreMetrics,
        ElementAnalysisData
    )
except ImportError:
    # Handle relative import issues for testing
    import sys
    from pathlib import Path
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir.parent))
    
    from config.settings import settings
    from core.exceptions import VectorStoreError, VectorStoreConnectionError
    from schemas.vector_store_schemas import (
        DOMElementData,
        GherkinStepData,
        VectorSearchRequest,
        VectorSearchResponse,
        VectorStoreMetrics,
        ElementAnalysisData
    )


@runtime_checkable
class ElementAnalysisLike(Protocol):
    """Protocol defining the required shape of ElementAnalysis for type safety."""
    locators: List[Dict[str, Any]]
    
    def get_description_string(self) -> str: ...
    def to_dict(self) -> Dict[str, Any]: ...


class VectorStoreService:
    """
    Enterprise-grade vector store service providing comprehensive storage and retrieval
    capabilities for DOM elements and Gherkin steps with full audit logging and security.
    """
    
    _instance: Optional[VectorStoreService] = None
    _instance_lock = asyncio.Lock()
    _initialized = False
    
    def __init__(self) -> None:
        """Initialize the vector store service with enterprise configuration."""
        if VectorStoreService._instance is not None:
            raise RuntimeError("VectorStoreService is a singleton. Use get_instance() method.")
        
        self.client: Optional[chromadb.Client] = None
        self.embedding_function: Optional[Any] = None
        self.dom_collection: Optional[Collection] = None
        self.gherkin_collection: Optional[Collection] = None
        
        # Metrics tracking
        self.metrics = VectorStoreMetrics()
        
        # Configuration
        self.dom_collection_name = settings.mcp_vector_dom_collection
        self.gherkin_collection_name = settings.mcp_vector_gherkin_collection
        self.embedding_model = settings.mcp_vector_embedding_model
        self.persist_path = settings.mcp_vector_persist_path
        
        logger.info(
            "VectorStoreService initialized",
            extra={
                "service": "vector_store",
                "action": "initialize",
                "dom_collection": self.dom_collection_name,
                "gherkin_collection": self.gherkin_collection_name,
                "embedding_model": self.embedding_model,
                "persist_path": self.persist_path,
                "audit": True
            }
        )
    
    @classmethod
    async def get_instance(cls) -> VectorStoreService:
        """Get the singleton instance of VectorStoreService in a thread-safe way."""
        if cls._instance is None:
            async with cls._instance_lock:
                if cls._instance is None:
                    logger.info("Creating new VectorStoreService singleton instance")
                    cls._instance = cls()
                    await cls._instance._initialize()
        return cls._instance
    
    async def _initialize(self) -> None:
        """Initialize ChromaDB client and collections with enterprise patterns."""
        if self._initialized:
            return
        
        try:
            logger.info("Initializing ChromaDB client and collections")
            
            # Initialize ChromaDB client
            await self._initialize_client()
            
            # Initialize embedding function
            await self._initialize_embedding_function()
            
            # Initialize collections
            await self._initialize_collections()
            
            self._initialized = True
            
            logger.info(
                "VectorStoreService fully initialized",
                extra={
                    "service": "vector_store",
                    "action": "initialize_complete",
                    "dom_collection_ready": self.dom_collection is not None,
                    "gherkin_collection_ready": self.gherkin_collection is not None,
                    "audit": True
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to initialize VectorStoreService: {e}",
                extra={
                    "service": "vector_store",
                    "action": "initialize_error",
                    "error": str(e),
                    "audit": True
                },
                exc_info=True
            )
            raise VectorStoreConnectionError(f"Failed to initialize vector store: {e}")
    
    async def _initialize_client(self) -> None:
        """Initialize ChromaDB client with configuration-driven setup."""
        try:
            if self.persist_path and self.persist_path.lower() != "memory":
                # Create persistent storage directory
                os.makedirs(self.persist_path, exist_ok=True)
                self.client = chromadb.PersistentClient(path=self.persist_path)
                logger.info(f"Initialized persistent ChromaDB client at: {self.persist_path}")
            else:
                # Use in-memory client for testing/development
                self.client = chromadb.Client()
                logger.info("Initialized in-memory ChromaDB client")
                
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}")
            raise VectorStoreConnectionError(f"ChromaDB client initialization failed: {e}")
    
    async def _initialize_embedding_function(self) -> None:
        """Initialize embedding function with enterprise configuration."""
        try:
            self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model
            )
            logger.info(f"Initialized embedding function with model: {self.embedding_model}")
            
        except Exception as e:
            logger.error(f"Failed to initialize embedding function: {e}")
            raise VectorStoreConnectionError(f"Embedding function initialization failed: {e}")
    
    async def _initialize_collections(self) -> None:
        """Initialize ChromaDB collections with error recovery."""
        try:
            # Initialize DOM collection
            await self._initialize_dom_collection()
            
            # Initialize Gherkin collection
            await self._initialize_gherkin_collection()
            
        except Exception as e:
            logger.error(f"Failed to initialize collections: {e}")
            raise VectorStoreConnectionError(f"Collections initialization failed: {e}")
    
    async def _initialize_dom_collection(self) -> None:
        """Initialize DOM elements collection with error handling."""
        try:
            self.dom_collection = self.client.get_or_create_collection(
                name=self.dom_collection_name,
                embedding_function=self.embedding_function
            )
            logger.info(f"DOM collection '{self.dom_collection_name}' initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize DOM collection: {e}")
            # Attempt recovery
            await self._attempt_collection_recovery(self.dom_collection_name, "DOM")
    
    async def _initialize_gherkin_collection(self) -> None:
        """Initialize Gherkin steps collection with error handling."""
        try:
            self.gherkin_collection = self.client.get_or_create_collection(
                name=self.gherkin_collection_name,
                embedding_function=self.embedding_function
            )
            logger.info(f"Gherkin collection '{self.gherkin_collection_name}' initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Gherkin collection: {e}")
            # Attempt recovery
            await self._attempt_collection_recovery(self.gherkin_collection_name, "Gherkin")
    
    async def _attempt_collection_recovery(self, collection_name: str, collection_type: str) -> None:
        """Attempt to recover from collection initialization errors."""
        try:
            if "no such table" in str(Exception()).lower():
                logger.warning(f"Attempting database recovery for {collection_type} collection")
                
                # Reset client for recovery
                if self.persist_path and self.persist_path.lower() != "memory":
                    self.client = chromadb.PersistentClient(
                        path=self.persist_path,
                        settings=chromadb.Settings(allow_reset=True)
                    )
                    try:
                        self.client.reset()
                        logger.info("ChromaDB reset successful")
                    except Exception as reset_err:
                        logger.error(f"Failed to reset ChromaDB: {reset_err}")
                else:
                    self.client = chromadb.Client()
                
                # Retry collection creation
                collection = self.client.get_or_create_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function
                )
                
                if collection_type == "DOM":
                    self.dom_collection = collection
                else:
                    self.gherkin_collection = collection
                
                logger.info(f"Successfully recovered {collection_type} collection after reset")
                
        except Exception as recovery_error:
            logger.error(f"Collection recovery failed for {collection_type}: {recovery_error}")
            raise VectorStoreConnectionError(f"Failed to recover {collection_type} collection")
    
    def _generate_stable_element_id(
        self, 
        page_url: str, 
        element_metadata: Dict[str, Any], 
        element_locators: List[Dict[str, Any]]
    ) -> str:
        """Generate stable, deterministic ID for DOM elements."""
        hasher = hashlib.sha1()
        
        # Include page URL
        hasher.update(page_url.encode('utf-8'))
        
        # Include element properties
        hasher.update(element_metadata.get('tag', '').encode('utf-8'))
        
        # Include key attributes
        attributes = element_metadata.get('attributes', {})
        for key in ['id', 'name', 'data-testid', 'placeholder', 'role', 'type']:
            val = attributes.get(key)
            if val:
                hasher.update(str(val).encode('utf-8'))
        
        # Include best locator
        if element_locators:
            best_locator = element_locators[0]
            hasher.update(
                f"{best_locator.get('strategy', '')}:"
                f"{best_locator.get('value', '')}::"
                f"{best_locator.get('options', '')}".encode('utf-8')
            )
        
        # Include accessible name or text
        name_or_text = element_metadata.get('accessible_name') or element_metadata.get('text')
        if name_or_text:
            hasher.update(name_or_text.encode('utf-8'))
        
        return hasher.hexdigest()[:16]
    
    def _generate_gherkin_step_id(self, step_text: str) -> str:
        """Generate stable ID for Gherkin steps."""
        # Clean the step text for consistent hashing
        clean_text = step_text.strip().lower()
        # Remove common Gherkin keywords for better deduplication
        for keyword in ['given ', 'when ', 'then ', 'and ', 'but ']:
            if clean_text.startswith(keyword):
                clean_text = clean_text[len(keyword):]
                break
        
        # Generate hash-based ID
        hasher = hashlib.sha1()
        hasher.update(clean_text.encode('utf-8'))
        return f"step_{hasher.hexdigest()[:12]}"
    
    async def add_or_update_elements(
        self, 
        page_url: str, 
        element_analyses: List[ElementAnalysisLike],
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add or update DOM elements in vector store with audit logging."""
        if not self.dom_collection:
            raise VectorStoreError("DOM collection not initialized")
        
        if not element_analyses:
            logger.warning("Empty element analyses list provided")
            return
        
        start_time = datetime.utcnow()
        
        logger.info(
            f"Adding/updating {len(element_analyses)} elements for page: {page_url}",
            extra={
                "service": "vector_store",
                "action": "add_elements",
                "page_url": page_url,
                "element_count": len(element_analyses),
                "context": context,
                "audit": True
            }
        )
        
        try:
            # Prepare batch data
            docs = []
            ids = []
            metadatas = []
            
            for element in element_analyses:
                if not element.locators:
                    continue
                
                # Generate stable ID
                element_dict = element.to_dict()
                element_meta = element_dict.get("metadata", {})
                elem_id = self._generate_stable_element_id(page_url, element_meta, element.locators)
                
                # Prepare document and metadata
                element_description = element.get_description_string()
                metadata = {
                    "page_url": page_url,
                    "description": element_description,
                    "locators": element.locators,
                    "timestamp": datetime.utcnow().isoformat(),
                    "context": context or {}
                }
                
                # Add element properties to metadata
                for key in ["tag", "role", "type"]:
                    if key in element_meta:
                        metadata[key] = element_meta[key]
                
                # Add element ID if available
                element_id = element_meta.get("attributes", {}).get("id")
                if element_id:
                    metadata["element_id"] = element_id
                
                docs.append(element_description)
                ids.append(elem_id)
                metadatas.append(metadata)
            
            if not ids:
                logger.warning("No valid elements to add to vector store")
                return
            
            # Execute batch upsert
            self.dom_collection.upsert(
                documents=docs,
                ids=ids,
                metadatas=metadatas
            )
            
            # Update metrics
            self.metrics.dom_elements_stored += len(ids)
            self.metrics.last_dom_update = datetime.utcnow()
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(
                f"Successfully added/updated {len(ids)} elements in {duration:.2f}s",
                extra={
                    "service": "vector_store",
                    "action": "add_elements_complete",
                    "page_url": page_url,
                    "elements_processed": len(ids),
                    "duration_seconds": duration,
                    "audit": True
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error adding/updating elements: {e}",
                extra={
                    "service": "vector_store",
                    "action": "add_elements_error",
                    "page_url": page_url,
                    "error": str(e),
                    "audit": True
                },
                exc_info=True
            )
            raise VectorStoreError(f"Failed to add/update elements: {e}")
    
    async def query_elements(
        self,
        query_description: str,
        page_url: Optional[str] = None,
        n_results: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query vector store for elements matching description with audit logging."""
        if not self.dom_collection:
            raise VectorStoreError("DOM collection not initialized")
        
        start_time = datetime.utcnow()
        
        logger.info(
            f"Querying elements: '{query_description}'",
            extra={
                "service": "vector_store",
                "action": "query_elements",
                "query": query_description,
                "page_url": page_url,
                "n_results": n_results,
                "filters": filters,
                "context": context,
                "audit": True
            }
        )
        
        try:
            # Build where clause
            where_clause = {}
            if page_url and page_url != "_unknown_url_":
                where_clause["page_url"] = page_url
            if filters:
                where_clause.update(filters)
            
            # Execute query
            results = self.dom_collection.query(
                query_texts=[query_description],
                n_results=n_results,
                where=where_clause if where_clause else None,
                include=['metadatas', 'documents', 'distances']
            )
            
            # Process results
            processed_results = []
            if results and results.get('ids'):
                result_ids = results['ids'][0]
                distances = results.get('distances', [[]])[0]
                metadatas_list = results.get('metadatas', [[]])[0]
                
                for i, elem_id in enumerate(result_ids):
                    metadata = metadatas_list[i] if i < len(metadatas_list) else {}
                    distance = distances[i] if i < len(distances) else None
                    
                    # Parse locators if stored as JSON string
                    locators = metadata.get('locators', [])
                    if isinstance(locators, str):
                        try:
                            locators = json.loads(locators)
                        except json.JSONDecodeError:
                            locators = []
                    
                    processed_results.append({
                        'id': elem_id,
                        'description': metadata.get('description', ''),
                        'metadata': metadata,
                        'locators': locators,
                        'distance': distance
                    })
                
                # Sort by distance (lower is better)
                processed_results.sort(
                    key=lambda x: float('inf') if x.get('distance') is None else x.get('distance')
                )
            
            # Update metrics
            self.metrics.dom_queries_executed += 1
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(
                f"Query completed: found {len(processed_results)} matches in {duration:.2f}s",
                extra={
                    "service": "vector_store",
                    "action": "query_elements_complete",
                    "query": query_description,
                    "results_count": len(processed_results),
                    "duration_seconds": duration,
                    "audit": True
                }
            )
            
            return processed_results
            
        except Exception as e:
            logger.error(
                f"Error querying elements: {e}",
                extra={
                    "service": "vector_store",
                    "action": "query_elements_error",
                    "query": query_description,
                    "error": str(e),
                    "audit": True
                },
                exc_info=True
            )
            raise VectorStoreError(f"Failed to query elements: {e}")
    
    async def add_gherkin_steps(
        self,
        steps: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add Gherkin steps to vector store with deduplication and audit logging."""
        if not self.gherkin_collection:
            raise VectorStoreError("Gherkin collection not initialized")
        
        if not steps:
            logger.warning("Empty Gherkin steps list provided")
            return
        
        start_time = datetime.utcnow()
        
        logger.info(
            f"Adding {len(steps)} Gherkin steps",
            extra={
                "service": "vector_store",
                "action": "add_gherkin_steps",
                "steps_count": len(steps),
                "context": context,
                "audit": True
            }
        )
        
        try:
            docs = []
            ids = []
            metadatas = []
            
            for step in steps:
                step_text = step.strip()
                if not step_text:
                    continue
                
                step_id = self._generate_gherkin_step_id(step_text)
                metadata = {
                    "step_text": step_text,
                    "timestamp": datetime.utcnow().isoformat(),
                    "context": context or {}
                }
                
                docs.append(step_text)
                ids.append(step_id)
                metadatas.append(metadata)
            
            if not ids:
                logger.warning("No valid Gherkin steps to add")
                return
            
            # Execute batch upsert
            self.gherkin_collection.upsert(
                documents=docs,
                ids=ids,
                metadatas=metadatas
            )
            
            # Update metrics
            self.metrics.gherkin_steps_stored += len(ids)
            self.metrics.last_gherkin_update = datetime.utcnow()
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(
                f"Successfully added {len(ids)} Gherkin steps in {duration:.2f}s",
                extra={
                    "service": "vector_store",
                    "action": "add_gherkin_steps_complete",
                    "steps_processed": len(ids),
                    "duration_seconds": duration,
                    "audit": True
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error adding Gherkin steps: {e}",
                extra={
                    "service": "vector_store",
                    "action": "add_gherkin_steps_error",
                    "error": str(e),
                    "audit": True
                },
                exc_info=True
            )
            raise VectorStoreError(f"Failed to add Gherkin steps: {e}")
    
    async def query_gherkin_steps(
        self,
        query_text: str,
        n_results: int = 3,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query Gherkin steps with similarity matching and audit logging."""
        if not self.gherkin_collection:
            raise VectorStoreError("Gherkin collection not initialized")
        
        start_time = datetime.utcnow()
        
        logger.info(
            f"Querying Gherkin steps: '{query_text}'",
            extra={
                "service": "vector_store",
                "action": "query_gherkin_steps",
                "query": query_text,
                "n_results": n_results,
                "context": context,
                "audit": True
            }
        )
        
        try:
            results = self.gherkin_collection.query(
                query_texts=[query_text],
                n_results=n_results,
                include=['metadatas', 'documents', 'distances']
            )
            
            processed_results = []
            if results and results.get('ids'):
                result_ids = results['ids'][0]
                distances = results.get('distances', [[]])[0]
                metadatas_list = results.get('metadatas', [[]])[0]
                documents = results.get('documents', [[]])[0]
                
                for i, step_id in enumerate(result_ids):
                    metadata = metadatas_list[i] if i < len(metadatas_list) else {}
                    distance = distances[i] if i < len(distances) else None
                    document = documents[i] if i < len(documents) else ""
                    
                    processed_results.append({
                        'id': step_id,
                        'step_text': document,
                        'metadata': metadata,
                        'distance': distance
                    })
                
                # Sort by distance
                processed_results.sort(
                    key=lambda x: float('inf') if x.get('distance') is None else x.get('distance')
                )
            
            # Update metrics
            self.metrics.gherkin_queries_executed += 1
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(
                f"Gherkin query completed: found {len(processed_results)} matches in {duration:.2f}s",
                extra={
                    "service": "vector_store",
                    "action": "query_gherkin_steps_complete",
                    "query": query_text,
                    "results_count": len(processed_results),
                    "duration_seconds": duration,
                    "audit": True
                }
            )
            
            return processed_results
            
        except Exception as e:
            logger.error(
                f"Error querying Gherkin steps: {e}",
                extra={
                    "service": "vector_store",
                    "action": "query_gherkin_steps_error",
                    "query": query_text,
                    "error": str(e),
                    "audit": True
                },
                exc_info=True
            )
            raise VectorStoreError(f"Failed to query Gherkin steps: {e}")
    
    async def clear_page_elements(self, page_url: str) -> None:
        """Clear all elements for a specific page with audit logging."""
        if not self.dom_collection:
            raise VectorStoreError("DOM collection not initialized")
        
        logger.info(
            f"Clearing elements for page: {page_url}",
            extra={
                "service": "vector_store",
                "action": "clear_page_elements",
                "page_url": page_url,
                "audit": True
            }
        )
        
        try:
            # Query elements for the page
            results = self.dom_collection.query(
                query_texts=[""],
                n_results=1000,  # Large number to get all elements
                where={"page_url": page_url},
                include=['ids']
            )
            
            if results and results.get('ids') and results['ids'][0]:
                element_ids = results['ids'][0]
                self.dom_collection.delete(ids=element_ids)
                
                logger.info(
                    f"Cleared {len(element_ids)} elements for page: {page_url}",
                    extra={
                        "service": "vector_store",
                        "action": "clear_page_elements_complete",
                        "page_url": page_url,
                        "elements_cleared": len(element_ids),
                        "audit": True
                    }
                )
            else:
                logger.info(f"No elements found to clear for page: {page_url}")
                
        except Exception as e:
            logger.error(
                f"Error clearing page elements: {e}",
                extra={
                    "service": "vector_store",
                    "action": "clear_page_elements_error",
                    "page_url": page_url,
                    "error": str(e),
                    "audit": True
                },
                exc_info=True
            )
            raise VectorStoreError(f"Failed to clear page elements: {e}")
    
    async def get_metrics(self) -> VectorStoreMetrics:
        """Get current vector store metrics."""
        return self.metrics
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on vector store service."""
        try:
            status = {
                "service": "vector_store",
                "status": "healthy",
                "initialized": self._initialized,
                "dom_collection_ready": self.dom_collection is not None,
                "gherkin_collection_ready": self.gherkin_collection is not None,
                "embedding_model": self.embedding_model,
                "metrics": self.metrics.dict()
            }
            
            # Test collections if available
            if self.dom_collection:
                try:
                    self.dom_collection.count()
                    status["dom_collection_status"] = "operational"
                except Exception as e:
                    status["dom_collection_status"] = f"error: {e}"
                    status["status"] = "degraded"
            
            if self.gherkin_collection:
                try:
                    self.gherkin_collection.count()
                    status["gherkin_collection_status"] = "operational"
                except Exception as e:
                    status["gherkin_collection_status"] = f"error: {e}"
                    status["status"] = "degraded"
            
            return status
            
        except Exception as e:
            return {
                "service": "vector_store",
                "status": "unhealthy",
                "error": str(e)
            } 