# Architecture

## Component Interaction

```mermaid
graph TD
    User([User Query]) --> API[FastAPI Entry]
    
    subgraph Self-RAG Pipeline
        API --> Classify{Needs Retrieval?}
        Classify -- No --> Direct[Direct LLM Answer]
        Classify -- Yes --> Retrieve[Hybrid Search Engine]
        
        Retrieve --> Vector[Qdrant Vector Search\n1024d Dense]
        Retrieve --> Sparse[BM25 Keyword Search]
        
        Vector --> RRF[RRF Score Fusion]
        Sparse --> RRF
        
        RRF --> Rerank[Cross-Encoder Reranking\nBGE-Reranker]
        
        Rerank --> Gen[LLM Generation\nQwen3 via Ollama]
        
        Gen --> Validate{Grounded?}
        Validate -- Fail --> Fallback[Extractive Fallback]
        Validate -- Pass --> Output[Final Response]
    end
    
    subgraph Data Pipeline
        PDF[PDF Upload] --> Extract[PyMuPDF Text & Tables]
        Extract --> Hierarchy[Chapter/Section Detection]
        Hierarchy --> Chunk[Hierarchy-Aware Chunker]
        
        Chunk --> Embed[BGE-M3 Embedder]
        Embed --> Upsert[(Qdrant DB)]
        Chunk --> BM25[(In-Memory BM25)]
        Chunk --> PIndex[(Hierarchical PageIndex)]
    end
```

## Data Schema

### Chunk Payload (Qdrant)
```json
{
  "chunk_id": "uuid",
  "manual_id": "uuid",
  "manual_name": "Robot Arm Setup",
  "filename": "robot_arm_v2.pdf",
  "chapter": "3. Maintenance",
  "section": "3.1 Lubrication",
  "page": 42,
  "chunk_index": 125,
  "text": "Apply 10ml of grease...",
  "content_type": "text",
  "hierarchy_path": "Robot Arm Setup > 3. Maintenance > 3.1 Lubrication",
  "has_tables": false
}
```
