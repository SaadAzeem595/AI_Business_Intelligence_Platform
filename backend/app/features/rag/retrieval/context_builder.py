from typing import List, Tuple
from app.features.rag.schemas import RetrievalResult

class ContextBuilder:
    @staticmethod
    def build_context(results: List[RetrievalResult], max_tokens: int = 3000) -> Tuple[str, int]:
        """
        Assembles a structured prompt context from retrieval results, ensuring
        we stay within a token budget (using 4 characters per token as an approximation).
        """
        # Character-based approximation of token limits (1 token ~ 4 characters)
        char_limit = max_tokens * 4
        
        context_blocks = []
        current_chars = 0
        
        for idx, res in enumerate(results):
            # Format citation info as metadata headers
            cite = res.citation
            ref_info = f"Document: {cite.filename}"
            if cite.page:
                ref_info += f" | Page: {cite.page}"
            if cite.heading:
                ref_info += f" | Section: {cite.heading}"
                
            block = f"[Source Reference #{idx + 1} - {ref_info}]\n{res.text}\n\n"
            block_len = len(block)
            
            if current_chars + block_len > char_limit:
                # Truncate and add a marker
                allowable = char_limit - current_chars
                if allowable > 100:
                    context_blocks.append(block[:allowable] + "... [Truncated due to context token budget]\n\n")
                    current_chars += allowable
                break
            else:
                context_blocks.append(block)
                current_chars += block_len
                
        full_context = "".join(context_blocks).strip()
        approx_tokens = int(current_chars / 4)
        
        return full_context, approx_tokens
