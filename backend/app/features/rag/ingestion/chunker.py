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

    def _chunk_tabular_text(self, text: str, max_rows_per_chunk: int = 50) -> List[Dict[str, Any]]:
        """
        Processes structured tabular data ([TABULAR_DATA: ...], [SCHEMA: ...])
        into human-readable chunks containing Schema metadata, Dataset Summaries,
        and Markdown tables with explicit row context.
        """
        chunks = []
        table_blocks = text.split("[TABULAR_DATA:")
        
        for block in table_blocks:
            if not block.strip():
                continue
                
            lines = block.strip().split("\n")
            title_line = lines[0].split("]")[0].strip() if "]" in lines[0] else "Tabular Dataset"
            
            schema_cols = []
            schema_details_str = ""
            dataset_summary_str = ""
            row_lines = []
            
            for line in lines[1:]:
                line_str = line.strip()
                if line_str.startswith("[SCHEMA:"):
                    cols_raw = line_str.replace("[SCHEMA:", "").rstrip("]").strip()
                    schema_cols = [c.strip() for c in cols_raw.split("|") if c.strip()]
                elif line_str.startswith("[DATASET_SCHEMA_DETAILS:"):
                    schema_details_str = line_str.replace("[DATASET_SCHEMA_DETAILS:", "").rstrip("]").strip()
                elif line_str.startswith("[DATASET_SUMMARY:"):
                    dataset_summary_str = line_str.replace("[DATASET_SUMMARY:", "").rstrip("]").strip()
                elif line_str.startswith("Row "):
                    row_lines.append(line_str)
                    
            cols_joined = " | ".join(schema_cols) if schema_cols else "Columns"

            # 1. Batch rows into row-group chunks first
            if row_lines:
                for i in range(0, len(row_lines), max_rows_per_chunk):
                    batch = row_lines[i:i + max_rows_per_chunk]
                    start_row = i + 1
                    end_row = i + len(batch)
                    
                    heading_name = f"{title_line} (Rows {start_row}-{end_row})"
                    
                    # Build Markdown table representation
                    md_table_lines = [
                        f"### Dataset: {title_line} (Rows {start_row}-{end_row})",
                        f"Schema: {cols_joined}",
                        "",
                        f"| {' | '.join(schema_cols)} |" if schema_cols else "| Data |",
                        f"| {' | '.join(['---'] * len(schema_cols))} |" if schema_cols else "| --- |"
                    ]
                    
                    # Convert `Row X -> Col1: Val1 | Col2: Val2` to markdown table row
                    for r_str in batch:
                        if " -> " in r_str:
                            kv_part = r_str.split(" -> ")[1]
                            kvs = dict(item.split(": ", 1) for item in kv_part.split(" | ") if ": " in item)
                            row_vals = [str(kvs.get(col, "")).strip() for col in schema_cols]
                            md_table_lines.append(f"| {' | '.join(row_vals)} |")
                        else:
                            md_table_lines.append(f"| {r_str} |")
                            
                    md_table_lines.append("")
                    md_table_lines.append("Row Context:")
                    md_table_lines.extend(batch)
                    
                    chunk_text = "\n".join(md_table_lines)
                    chunks.append({
                        "text": chunk_text,
                        "heading": heading_name,
                        "chunk_type": "table_rows",
                        "row_start": start_row,
                        "row_end": end_row,
                        "columns": schema_cols,
                        "table_name": title_line
                    })

            # 2. Generate Schema Chunk
            schema_text_lines = [
                f"### Dataset Schema: {title_line}",
                f"Columns ({len(schema_cols)}): {cols_joined}"
            ]
            if schema_details_str:
                schema_text_lines.append(f"Field Types & Missing Counts: {schema_details_str}")
            schema_chunk_text = "\n".join(schema_text_lines)
            chunks.append({
                "text": schema_chunk_text,
                "heading": f"Dataset Schema: {title_line}",
                "chunk_type": "dataset_schema",
                "row_start": None,
                "row_end": None,
                "columns": schema_cols,
                "table_name": title_line
            })

            # 3. Generate Dataset Summary Chunk (if available)
            if dataset_summary_str:
                summary_chunk_text = f"### Dataset Summary: {title_line}\n{dataset_summary_str}"
                chunks.append({
                    "text": summary_chunk_text,
                    "heading": f"Dataset Summary: {title_line}",
                    "chunk_type": "dataset_summary",
                    "row_start": None,
                    "row_end": None,
                    "columns": schema_cols,
                    "table_name": title_line
                })
                
        return chunks

    def chunk_by_heading(self, text: str) -> List[Dict[str, Any]]:
        """
        Chunks the document text while keeping track of headings.
        Detects tabular datasets, markdown headers, PPTX slides, and Excel sheets.
        """
        if not text:
            return []
            
        # Check if input text is structured tabular data from CsvParser / ExcelParser
        if "[TABULAR_DATA:" in text and "[SCHEMA:" in text:
            tabular_chunks = self._chunk_tabular_text(text)
            if tabular_chunks:
                return tabular_chunks

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
