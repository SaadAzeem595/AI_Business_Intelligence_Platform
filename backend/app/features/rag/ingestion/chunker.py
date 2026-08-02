import re
from typing import List, Dict, Any

class ChunkerService:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_fixed_size(self, text: str) -> List[str]:
        """Simple fixed-size word chunker to avoid cutting off words."""
        if not text:
            return []
            
        words = text.split()
        chunks = []
        
        # Assume average word length is 5 characters
        words_per_chunk = max(1, self.chunk_size // 5)
        words_overlap = max(0, self.chunk_overlap // 5)
        
        i = 0
        while i < len(words):
            chunk_words = words[i:i + words_per_chunk]
            chunks.append(" ".join(chunk_words))
            i += words_per_chunk - words_overlap
            if words_per_chunk - words_overlap <= 0:
                break
        return chunks

    def chunk_by_heading(self, text: str) -> List[Dict[str, Any]]:
        """
        Chunks the document text while keeping track of headings.
        Detects markdown headers, PPTX slides, and Excel sheets.
        """
        if not text:
            return []
            
        lines = text.split("\n")
        current_heading = "Introduction"
        heading_sections = []
        current_section = []
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
                
            # Detect Markdown header
            if line_stripped.startswith(("#", "##", "###", "####")):
                if current_section:
                    heading_sections.append((current_heading, "\n".join(current_section)))
                current_heading = line_stripped.lstrip("#").strip()
                current_section = [line]
            # Detect Slide/Sheet header
            elif line_stripped.startswith("--- ") and line_stripped.endswith(" ---"):
                if current_section:
                    heading_sections.append((current_heading, "\n".join(current_section)))
                current_heading = line_stripped.replace("---", "").strip()
                current_section = [line]
            else:
                current_section.append(line)
                
        if current_section:
            heading_sections.append((current_heading, "\n".join(current_section)))
            
        chunks = []
        for heading, sect_text in heading_sections:
            sect_chunks = self.chunk_fixed_size(sect_text)
            for chunk_text in sect_chunks:
                chunks.append({
                    "text": chunk_text,
                    "heading": heading
                })
                
        # If no heading-based sections were found, split everything under "Introduction"
        if not chunks and text.strip():
            sect_chunks = self.chunk_fixed_size(text)
            for chunk_text in sect_chunks:
                chunks.append({
                    "text": chunk_text,
                    "heading": "Introduction"
                })
                
        return chunks
