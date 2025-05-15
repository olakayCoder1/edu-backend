from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv
import json
import re
from typing import List, Dict, Any
from PyPDF2 import PdfReader
from docx import Document

load_dotenv()

def estimate_tokens(text: str) -> int:
    """Estimate number of tokens in text."""
    return int(len(text) / 4)  # average 4 characters per token

class ContentStructurer:
    """
    Enhanced document processor with improved text cleaning, structure detection, and error handling.
    Supports PDF, DOCX, and TXT files with section-aware chunking.
    """

    def __init__(self, model, max_tokens: int = 2000):
        self.model = model
        self.max_tokens = max_tokens
        self.section_pattern = re.compile(
            r'(^(chapter|section|module|unit|lesson|part)\s+\d+|[\d.]+[\s]?.+)$', 
            re.IGNORECASE | re.MULTILINE
        )

    def parse_pdf(self, pdf_path: str) -> str:
        """Improved PDF parsing with section detection and text normalization"""
        try:
            reader = PdfReader(pdf_path)
            text = []
            current_section = []
            
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    # Normalize text and detect sections
                    cleaned = self._clean_text(page_text)
                    sections = self._split_sections(cleaned)
                    
                    for section in sections:
                        if self._is_section_header(section):
                            if current_section:
                                text.append(" ".join(current_section))
                            current_section = [section]
                        else:
                            current_section.append(section)
            
            if current_section:
                text.append(" ".join(current_section))
                
            return "\n\n".join(text)
            
        except Exception as e:
            raise RuntimeError(f"PDF parsing failed: {str(e)}")

    def parse_docx(self, docx_path: str) -> str:
        """DOCX parser that preserves heading structure and lists"""
        try:
            doc = Document(docx_path)
            text = []
            current_section = []
            
            for para in doc.paragraphs:
                if para.style.name.lower().startswith('heading'):
                    if current_section:
                        text.append(" ".join(current_section))
                    current_section = [para.text]
                else:
                    current_section.append(para.text)
            
            if current_section:
                text.append(" ".join(current_section))
                
            return "\n\n".join(text)
            
        except Exception as e:
            raise RuntimeError(f"DOCX parsing failed: {str(e)}")

    def parse_document(self, file_path: str) -> str:
        """Main parsing method with validation and error handling"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        _, ext = os.path.splitext(file_path.lower())
        
        try:
            if ext == '.pdf':
                return self.parse_pdf(file_path)
            elif ext in ('.docx', '.doc'):
                return self.parse_docx(file_path)
            elif ext == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return self._clean_text(f.read())
            else:
                raise ValueError(f"Unsupported file type: {ext}")
        except Exception as e:
            raise RuntimeError(f"Document processing error: {str(e)}")

    def _clean_text(self, text: str) -> str:
        """Comprehensive text cleaning and normalization"""
        # Remove non-printable characters
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)
        # Fix hyphenated word breaks
        text = re.sub(r'(\w+)-\s+(\w+)', r'\1\2', text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove excessive newlines
        text = re.sub(r'\n+', '\n', text)
        return text.strip()

    def _is_section_header(self, text: str) -> bool:
        """Detects section headers using multiple heuristics"""
        text = text.strip()
        return (
            len(text) < 100 and  # Section headers are typically short
            (
                self.section_pattern.match(text) or
                text.isupper() or
                text.endswith(':')
            )
        )

    def _split_sections(self, text: str) -> List[str]:
        """Split text into potential sections using multiple delimiters"""
        return re.split(r'(\n\s*[\d.]+[\.\s].+?|\n\s*[A-Z][a-z]+:)', text)

    def chunk_content(self, content: str, max_chunks: int = None) -> List[str]:
        """
        Split content into smaller chunks suitable for model processing.
        Args:
            content: The text content to chunk
            max_chunks: Optional limit on number of chunks to create
        Returns:
            List of text chunks
        """
        # First split by meaningful section boundaries
        sections = content.split('\n\n')
        chunks = []
        current_chunk = []
        current_token_estimate = 0
        
        for section in sections:
            section_tokens = estimate_tokens(section)
            
            # If this section would make the chunk too big, start a new chunk
            if current_token_estimate + section_tokens > self.max_tokens:
                if current_chunk:  # Save the current chunk before starting a new one
                    chunks.append("\n\n".join(current_chunk))
                
                # For extremely large sections, split them further
                if section_tokens > self.max_tokens:
                    sentences = re.split(r'(?<=[.!?])\s+', section)
                    sub_chunk = []
                    sub_token_count = 0
                    
                    for sentence in sentences:
                        sentence_tokens = estimate_tokens(sentence)
                        if sub_token_count + sentence_tokens > self.max_tokens:
                            if sub_chunk:
                                chunks.append(" ".join(sub_chunk))
                            sub_chunk = [sentence]
                            sub_token_count = sentence_tokens
                        else:
                            sub_chunk.append(sentence)
                            sub_token_count += sentence_tokens
                    
                    if sub_chunk:
                        chunks.append(" ".join(sub_chunk))
                    
                    current_chunk = []
                    current_token_estimate = 0
                else:
                    current_chunk = [section]
                    current_token_estimate = section_tokens
            else:
                current_chunk.append(section)
                current_token_estimate += section_tokens
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))
            
        # Limit number of chunks if requested
        if max_chunks and len(chunks) > max_chunks:
            # Combine chunks to meet the max_chunks limit
            new_chunk_size = len(chunks) // max_chunks + (1 if len(chunks) % max_chunks else 0)
            new_chunks = []
            for i in range(0, len(chunks), new_chunk_size):
                new_chunks.append("\n\n".join(chunks[i:i+new_chunk_size]))
            chunks = new_chunks
            
        return chunks

    def create_prerequisite_graph(self, content: str, max_chunk_size: int = 2000, chunk_limit: int = None) -> List[Dict[str, Any]]:
        """
        Process content into modules with prerequisites, with improved chunking logic.
        Args:
            content: Document content
            max_chunk_size: Maximum token size for each chunk sent to the model
            chunk_limit: Optional maximum number of chunks to process
        Returns:
            List of module dictionaries
        """
        # Update max_tokens for chunking
        self.max_tokens = max_chunk_size
        
        # Create content chunks
        chunks = self.chunk_content(content, max_chunks=chunk_limit)
        print(f"Document split into {len(chunks)} chunks for processing")
        
        all_modules = []
        
        for idx, chunk in enumerate(chunks):
            try:
                print(f"Processing chunk {idx+1}/{len(chunks)}")
                prompt = (
                    f"Analyze this educational content and break it into logical modules with prerequisites.\n"
                    f"STRICT FORMATTING RULES:\n"
                    f"1. Escape all double quotes inside content with backslash (\\\")\n"
                    f"2. Use only double quotes for strings\n"
                    f"3. Ensure JSON is properly closed\n"
                    f"Format response as a JSON array with objects containing: "
                    f"name (string), summary (string), content (string), prerequisites (array of strings).\n"
                    f"Content chunk {idx+1}/{len(chunks)}:\n{chunk}\n"
                    f"Return ONLY valid JSON with proper escaping. No markdown or extra text."
                )
                response = self.model.invoke(prompt)

                if not response or not response.content:
                    print(f"Warning: Empty model response for chunk {idx+1}")
                    continue
                
                # Extract and clean JSON
                content_clean = self._clean_json_response(response.content)
                
                try:
                    modules_chunk = json.loads(content_clean)
                    
                    # Validate module structure
                    valid_modules = []
                    for mod in modules_chunk:
                        if all(key in mod for key in ['name', 'content']):
                            valid_modules.append({
                                'name': mod['name'].strip(),
                                'summary': mod.get('summary', '').strip(),
                                'content': mod['content'].strip(),
                                'prerequisites': [p.strip() for p in mod.get('prerequisites', [])]
                            })
                    
                    all_modules.extend(valid_modules)
                    print(f"Successfully processed {len(valid_modules)} modules from chunk {idx+1}")
                    
                except json.JSONDecodeError as e:
                    print(f"JSON Error in chunk {idx+1}: {str(e)}")
                    print(f"Problematic content (last 200 chars): {content_clean[-200:]}")
                    
                    # Try with more aggressive JSON repair
                    repaired = self._repair_json(content_clean)
                    try:
                        modules_chunk = json.loads(repaired)
                        valid_modules = []
                        for mod in modules_chunk:
                            if all(key in mod for key in ['name', 'content']):
                                valid_modules.append({
                                    'name': mod['name'].strip(),
                                    'summary': mod.get('summary', '').strip(), 
                                    'content': mod['content'].strip(),
                                    'prerequisites': [p.strip() for p in mod.get('prerequisites', [])]
                                })
                        all_modules.extend(valid_modules)
                        print(f"After repair: processed {len(valid_modules)} modules from chunk {idx+1}")
                    except:
                        print(f"JSON repair failed for chunk {idx+1}")
                
            except Exception as e:
                print(f"Error processing chunk {idx+1}: {str(e)}")
                continue
                
        # Deduplicate and finalize modules
        final_modules = self._deduplicate_modules(all_modules)
        print(f"Final module count after deduplication: {len(final_modules)}")
        return final_modules

    def _clean_json_response(self, response_content: str) -> str:
        """Improved JSON cleaning with robust extraction and error correction"""
        # Extract first potential JSON array/object
        json_match = re.search(r'(?s)(\[.*\])', response_content)
        if not json_match:
            json_match = re.search(r'(?s)(\{.*\})', response_content)
        
        content_clean = json_match.group(1) if json_match else response_content

        # Remove remaining markdown/formatting
        content_clean = re.sub(r'```(?:json)?', '', content_clean, flags=re.IGNORECASE)
        
        # Basic JSON repairs
        repairs = [
            (r'(?<!\\)"', '"'),        # Fix unescaped quotes
            (r'\\"(.*?)\\"', r'"\1"'), # Fix double-escaped quotes
            (r',\s*(?=[\]}])', ''),    # Remove trailing commas
            (r'[\x00-\x1f]', '')       # Remove control characters
        ]
        
        for pattern, replacement in repairs:
            content_clean = re.sub(pattern, replacement, content_clean)

        # Ensure proper termination
        if not content_clean.strip().endswith(']'):
            brackets_needed = content_clean.count('[') - content_clean.count(']')
            content_clean += ']' * max(0, brackets_needed)
            
        return content_clean.strip()

    def _repair_json(self, broken_json: str) -> str:
        """More aggressive JSON repair for severely malformed responses"""
        # Try to identify the array structure
        if not broken_json.startswith('['):
            broken_json = '[' + broken_json
        if not broken_json.endswith(']'):
            broken_json = broken_json + ']'

        # Fix missing quotes around keys
        broken_json = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', broken_json)
        
        # Fix unbalanced braces
        open_braces = broken_json.count('{')
        close_braces = broken_json.count('}')
        if open_braces > close_braces:
            broken_json += '}' * (open_braces - close_braces)
        
        # Fix missing commas between objects
        broken_json = re.sub(r'}\s*{', '},{', broken_json)
        
        return broken_json

    def _deduplicate_modules(self, modules: List[Dict]) -> List[Dict]:
        """Smart deduplication that merges similar modules"""
        seen = {}
        for mod in modules:
            key = mod['name'].lower()
            if key in seen:
                # Merge content and prerequisites
                seen[key]['content'] += "\n\n" + mod['content']
                seen[key]['prerequisites'] = list(
                    set(seen[key]['prerequisites'] + mod['prerequisites'])
                )
            else:
                seen[key] = mod
        return list(seen.values())
    
class QuizGenerator:
    """
    Generates quizzes for each module with improved handling of large content.
    """
    def __init__(self, model, max_content_tokens: int = 2000):
        self.model = model
        self.max_content_tokens = max_content_tokens

    def _chunk_module_content(self, content: str) -> List[str]:
        """Split large module content into manageable chunks"""
        if estimate_tokens(content) <= self.max_content_tokens:
            return [content]
        
        # Split by paragraphs
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = estimate_tokens(para)
            if current_tokens + para_tokens > self.max_content_tokens:
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                # Handle extremely long paragraphs
                if para_tokens > self.max_content_tokens:
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    sentence_chunk = []
                    sentence_tokens = 0
                    for sentence in sentences:
                        sent_tokens = estimate_tokens(sentence)
                        if sentence_tokens + sent_tokens > self.max_content_tokens:
                            if sentence_chunk:
                                chunks.append(' '.join(sentence_chunk))
                            sentence_chunk = [sentence]
                            sentence_tokens = sent_tokens
                        else:
                            sentence_chunk.append(sentence)
                            sentence_tokens += sent_tokens
                    if sentence_chunk:
                        chunks.append(' '.join(sentence_chunk))
                    current_chunk = []
                    current_tokens = 0
                else:
                    current_chunk = [para]
                    current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
        
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
            
        return chunks

    def generate_quiz(self, module: Dict[str, Any], extra_instruction: str = "") -> List[Dict[str, Any]]:
        """Generate quiz questions for a module, handling large content."""
        module_name = module['name']
        content = module['content']
        summary = module.get('summary', '')
        
        # For large modules, we need to chunk the content
        content_chunks = self._chunk_module_content(content)
        
        all_questions = []
        for i, chunk in enumerate(content_chunks):
            chunk_instruction = f"Content part {i+1}/{len(content_chunks)}" if len(content_chunks) > 1 else ""
            
            prompt = (
                f"Generate 3-5 quiz questions for module: {module_name}\n"
                f"Summary: {summary}\n"
                f"Content: {chunk}\n"
                f"{chunk_instruction}\n"
                f"Format each question as JSON with: question, options (array), answer, difficulty (1-5), topics (array)\n"
                f"{extra_instruction}\n"
                "Return only valid JSON array of questions. Ensure JSON is properly formatted with no markdown."
            )
            
            try:
                response = self.model.invoke(prompt)
                json_text = re.search(r'(?s)\[(.*)\]', response.content)
                if json_text:
                    clean_json = f"[{json_text.group(1)}]"
                else:
                    clean_json = response.content.strip()
                    if clean_json.startswith('```json'):
                        clean_json = clean_json[7:]
                    if clean_json.startswith('```'):
                        clean_json = clean_json[3:]
                    if clean_json.endswith('```'):
                        clean_json = clean_json[:-3]
                
                questions = json.loads(clean_json)
                
                # Add identifiers to questions
                for j, q in enumerate(questions):
                    q['id'] = f"q{i+1}_{j+1}"
                    if 'topics' not in q:
                        q['topics'] = [module_name]
                
                all_questions.extend(questions)
                print(f"Generated {len(questions)} questions from chunk {i+1}")
                
            except Exception as e:
                print(f"Quiz generation failed for chunk {i+1}: {str(e)}")
                
        # Deduplicate questions
        seen_questions = set()
        unique_questions = []
        
        for q in all_questions:
            q_text = q['question'].strip().lower()
            if q_text not in seen_questions:
                seen_questions.add(q_text)
                unique_questions.append(q)
                
        return unique_questions

class LangGraphAgent:
    """
    Main orchestrator that ties together all components with improved document handling.
    """
    def __init__(self, model, hints_db: Dict[str, str], max_chunk_size: int = 2000, chunk_limit: int = None):
        self.content_structurer = ContentStructurer(model, max_tokens=max_chunk_size)
        self.quiz_generator = QuizGenerator(model, max_content_tokens=max_chunk_size)
        self.chunk_limit = chunk_limit
        self.max_chunk_size = max_chunk_size

    def split_document(self, filepath: str, num_parts: int = 2) -> List[str]:
        """
        Split a document into multiple parts for easier processing.
        Args:
            filepath: Path to the document
            num_parts: Number of parts to split into
        Returns:
            List of content strings
        """
        try:
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"Document {filepath} not found")
                
            content = self.content_structurer.parse_document(filepath)
            if not content:
                raise ValueError("Document parsing returned empty content")
                
            # Split into roughly equal parts
            content_length = len(content)
            part_size = content_length // num_parts
            
            parts = []
            for i in range(num_parts):
                start = i * part_size
                end = (i + 1) * part_size if i < num_parts - 1 else content_length
                parts.append(content[start:end])
                
            print(f"Document split into {num_parts} parts")
            return parts
            
        except Exception as e:
            print(f"Document splitting failed: {str(e)}")
            return []

    def process_document_parts(self, content_parts: List[str]) -> List[Dict[str, Any]]:
        """
        Process multiple document parts and combine results.
        Args:
            content_parts: List of content strings from document parts
        Returns:
            Combined list of modules
        """
        all_modules = []
        
        for i, content in enumerate(content_parts):
            print(f"Processing document part {i+1}/{len(content_parts)}")
            try:
                modules = self.content_structurer.create_prerequisite_graph(
                    content, 
                    max_chunk_size=self.max_chunk_size,
                    chunk_limit=self.chunk_limit
                )
                all_modules.extend(modules)
                print(f"Part {i+1} generated {len(modules)} modules")
            except Exception as e:
                print(f"Error processing part {i+1}: {str(e)}")
                
        # Final deduplication of all modules
        final_modules = self.content_structurer._deduplicate_modules(all_modules)
        print(f"Final result: {len(final_modules)} unique modules")
        return final_modules

    def process_document(self, filepath: str, num_parts: int = 1) -> List[Dict[str, Any]]:
        """
        Process a document, optionally splitting it into parts first.
        Args:
            filepath: Path to the document
            num_parts: Number of parts to split the document into (1 for no splitting)
        Returns:
            List of modules
        """
        try:
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"Document {filepath} not found")
                
            if num_parts <= 1:
                content = self.content_structurer.parse_document(filepath)
                if not content:
                    raise ValueError("Document parsing returned empty content")
                    
                modules = self.content_structurer.create_prerequisite_graph(
                    content,
                    max_chunk_size=self.max_chunk_size,
                    chunk_limit=self.chunk_limit
                )
                if not modules:
                    print("Warning: No modules generated. Check document structure and model access.")
                return modules
            else:
                content_parts = self.split_document(filepath, num_parts)
                return self.process_document_parts(content_parts)
                
        except Exception as e:
            print(f"Document processing failed: {str(e)}")
            return []

# Example Usage:
# if __name__ == "__main__":
#     model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.2, api_key=os.getenv('GOOGLE_API_KEY'))
#     hints_db = {"Data communications": "Data communications refers to the transmission of digital data between two or more computers"}

#     # Create agent with smaller chunk size and optional limit
#     agent = LangGraphAgent(model, hints_db=hints_db, max_chunk_size=1500, chunk_limit=None)

#     try:
#         modules = agent.process_document("CSC_427_COMPUTER_NETWORK.pdf", num_parts=1)
        
#         if modules:
#             print(f"Successfully generated {len(modules)} modules")
            
#             # Save modules to file
#             with open("modules.json", "w") as f:
#                 json.dump(modules, f, indent=2)
            
#             # Generate and save quizzes for each module
#             all_quizzes = []
#             for module in modules:
#                 print(f"Generating quiz for module: {module['name']}")
#                 quiz = agent.quiz_generator.generate_quiz(module)
#                 if quiz:
#                     all_quizzes.append({
#                         "module_name": module["name"],
#                         "questions": quiz
#                     })
#                     print(f"Generated {len(quiz)} questions for {module['name']}")
            
#             # Save quizzes to file
#             if all_quizzes:
#                 with open("quizzes.json", "w") as f:
#                     json.dump(all_quizzes, f, indent=2)
#                 print(f"Saved {sum(len(q['questions']) for q in all_quizzes)} total questions to quizzes.json")
            
#     except Exception as e:
#         print(f"Fatal error: {str(e)}")