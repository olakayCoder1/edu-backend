import json
import re
import os
from dotenv import load_dotenv
from typing import Dict, List, Any
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

class AdaptiveQuiz:
    """
    Generates adaptive quizzes based on student performance data and module content.
    
    Args:
        model: The language model to use for quiz generation
        max_content_tokens: Maximum token size for content chunks (default: 2000)
        
    Student Performance Data Requirements:
    The student_data argument should be a dictionary containing:
    {
        "student_id": str,  # Unique identifier for the student
        "performance": {
            "topic_name": {
                "total_attempts": int,
                "correct_attempts": int,
                "last_attempted": str  # timestamp (optional)
            },
            ...
        },
        "preferences": {
            "difficulty_level": float,  # 0-1 scale (optional)
            "preferred_question_types": List[str]  # (optional)
        }
    }
    """
    
    def __init__(self, model, max_content_tokens: int = 2000):
        self.model = model
        self.max_content_tokens = max_content_tokens

    def _chunk_content(self, content: str) -> List[str]:
        """Split large content into manageable chunks"""
        if self._estimate_tokens(content) <= self.max_content_tokens:
            return [content]
        
        # Split by paragraphs
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = self._estimate_tokens(para)
            if current_tokens + para_tokens > self.max_content_tokens:
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
        
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
            
        return chunks

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (simplified)"""
        return len(text) // 4

    def _get_weak_topics(self, student_data: Dict[str, Any], module_topics: List[str]) -> List[str]:
        """Identify topics where student performance is below threshold"""
        weak_topics = []
        performance = student_data.get("performance", {})
        
        for topic in module_topics:
            topic_perf = performance.get(topic, {})
            total = topic_perf.get("total_attempts", 0)
            correct = topic_perf.get("correct_attempts", 0)
            
            if total > 0 and correct / total < 0.6:  # 60% accuracy threshold
                weak_topics.append(topic)
        
        return weak_topics

    def _generate_quiz_instructions(self, student_data: Dict[str, Any], module: Dict[str, Any]) -> str:
        """Create tailored instructions based on student data"""
        instructions = []
        
        # Add difficulty adjustment
        pref_diff = student_data.get("preferences", {}).get("difficulty_level", 0.5)
        if pref_diff <= 0.4:
            instructions.append("Generate easier questions suitable for beginners")
        elif pref_diff >= 0.7:
            instructions.append("Generate more challenging questions")
            
        # Add question type preferences
        pref_types = student_data.get("preferences", {}).get("preferred_question_types", [])
        if pref_types:
            instructions.append(f"Prefer these question types: {', '.join(pref_types)}")
            
        # Add focus on weak areas
        module_topics = module.get("topics", [module["name"]])
        weak_topics = self._get_weak_topics(student_data, module_topics)
        if weak_topics:
            instructions.append(f"Focus on these challenging topics: {', '.join(weak_topics)}")
            
        return ". ".join(instructions) + "." if instructions else ""

    def generate_quiz(self, student_data: Dict[str, Any], module: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate an adaptive quiz for a student based on their performance data.
        
        Args:
            student_data: Dictionary containing student performance information
            module: The module dictionary containing:
                   - name: str
                   - content: str
                   - summary: str (optional)
                   - topics: List[str] (optional)
                   
        Returns:
            List of quiz questions with:
            - question: str
            - options: List[str]
            - answer: str
            - difficulty: float (1-5)
            - topics: List[str]
        """
        module_name = module['name']
        content = module['content']
        summary = module.get('summary', '')
        
        # Generate tailored instructions
        extra_instruction = self._generate_quiz_instructions(student_data, module)
        
        # Process content in chunks if needed
        content_chunks = self._chunk_content(content)
        
        all_questions = []
        for i, chunk in enumerate(content_chunks):
            chunk_info = f"Content part {i+1}/{len(content_chunks)}" if len(content_chunks) > 1 else ""
            
            prompt = (
                f"Generate 3-5 quiz questions for module: {module_name}\n"
                f"Summary: {summary}\n"
                f"Content: {chunk}\n"
                f"{chunk_info}\n"
                f"{extra_instruction}\n"
                f"Format each question as JSON with: question, options (array), answer, difficulty (1-5), topics (array)\n"
                "Return only valid JSON array of questions. Ensure proper escaping and no markdown."
            )
            
            try:
                response = self.model.invoke(prompt)
                json_text = self._extract_json(response.content)
                questions = json.loads(json_text)
                
                # Add identifiers and ensure topics
                for j, q in enumerate(questions):
                    q['id'] = f"q{i+1}_{j+1}"
                    if 'topics' not in q:
                        q['topics'] = [module_name]
                
                all_questions.extend(questions)
                
            except Exception as e:
                print(f"Quiz generation failed for chunk {i+1}: {str(e)}")
                continue
                
        return self._deduplicate_questions(all_questions)

    def _extract_json(self, text: str) -> str:
        """Extract and clean JSON from model response"""
        # Try to find JSON array/object
        json_match = re.search(r'(?s)(\[.*\]|\{.*\})', text)
        if not json_match:
            return "[]"
        
        json_str = json_match.group(1)
        
        # Basic repairs
        json_str = re.sub(r'```(?:json)?', '', json_str, flags=re.IGNORECASE)
        json_str = json_str.replace('```', '')  # Remove code blocks
        json_str = re.sub(r'(?<!\\)"', '"', json_str)  # Fix escaping issues
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)  # Remove trailing commas
        
        return json_str

    def _deduplicate_questions(self, questions: List[Dict]) -> List[Dict]:
        """Remove duplicate questions"""
        seen = set()
        unique = []
        
        for q in questions:
            text = q['question'].lower().strip()
            if text not in seen:
                seen.add(text)
                unique.append(q)
                
        return unique

    def generate_quiz_by_modules(self, student_data: Dict[str, Any], weak_modules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate quizzes organized by module for weak modules.
        
        Args:
            student_data: Dictionary containing student performance information
            weak_modules: List of modules where student performance is weak
            
        Returns:
            List of dictionaries with:
            - module_name: str
            - questions: List[Dict] (questions for that module)
        """
        result = []
        
        for module in weak_modules:
            module_name = module['name']
            questions = self.generate_quiz(student_data, module)
            
            module_quiz = {
                "module_name": module_name,
                "questions": questions
            }
            
            result.append(module_quiz)
            
        return result
    
# Initialize with your language model
model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.2, api_key=os.getenv('GOOGLE_API_KEY'))
quiz_generator = AdaptiveQuiz(model)

# Sample student data
student_data = {
    "student_id": "123",
    "performance": {
        "Internet Model (TCP/IP)": {"total_attempts": 5, "correct_attempts": 2},
        "Network Layer Routing": {"total_attempts": 5, "correct_attempts": 1}
    },
    "preferences": {
        "difficulty_level": 0.3,
        "preferred_question_types": ["multiple_choice", "true_false"] # multiple-choice, true/false, short answer
    }
}

# Sample module
with open('modules.json', 'r') as file:
    modules = json.load(file)

weak_modules = []
for module in modules:
    module_name = module["name"]
    module_topics = module.get("topics", [module_name])  # Default to module name if no topics
    
    # Check performance for each topic in the module
    for topic in module_topics:
        topic_perf = student_data["performance"].get(topic, {})
        total = topic_perf.get("total_attempts", 0)
        correct = topic_perf.get("correct_attempts", 0)
        
        if total > 0 and (correct / total) < 0.6:  # 60% threshold
            weak_modules.append(module)
            break  # No need to check other topics if module is already marked as weak

# Generate quizzes for weak modules in the requested format
quizzes_by_module = quiz_generator.generate_quiz_by_modules(student_data, weak_modules)

print('Generating Quizzes')

# Output the quizzes in the required format
with open("Adaptive_quizzes.json", "w") as f:
    json.dump(quizzes_by_module, f, indent=2)