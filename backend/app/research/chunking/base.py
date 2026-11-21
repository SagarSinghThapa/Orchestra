from dataclasses import dataclass


@dataclass
class DocumentChunk:
    """
    Represents an atomic, page-bounded chunk of document text.
    
    Provenance Invariant:
    Every chunk belongs strictly to exactly one 1-indexed page_number (chunks never
    cross page boundaries). start_char and end_char index into the normalized page text.
    """
    chunk_id: str
    document_id: int
    project_id: int
    text: str
    chunk_index: int
    page_number: int  # 1-indexed; always exactly one page
    start_char: int   # Character offset within normalized page text
    end_char: int     # Character offset within normalized page text
    token_count: int
