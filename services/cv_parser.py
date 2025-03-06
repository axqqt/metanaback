import logging
import PyPDF2
import docx2txt
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from a .env file

logger = logging.getLogger(__name__)

class CVParser:
    """Service for parsing CVs and extracting information"""
    
    def extract_cv_info(self, file_path):
        """Extract information from CV"""
        text = ""
        file_ext = file_path.rsplit('.', 1)[1].lower()

        try:
            if file_ext == 'pdf':
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        text += page.extract_text()
            elif file_ext == 'docx':
                text = docx2txt.process(file_path)
        except Exception as e:
            logger.error(f"Error extracting text from CV: {e}")
            return {}

        # Parse the extracted text
        return self._parse_cv_text(text)
    
    def _parse_cv_text(self, text):
        """Parse CV text into structured sections"""
        # Simple parsing logic (can be enhanced with NLP/ML)
        sections = {
            'personal_info': {},
            'education': [],
            'qualifications': [],
            'projects': []
        }

        # Extract education (basic implementation)
        if "EDUCATION" in text.upper():
            education_section = text.upper().split("EDUCATION")[1].split(
                "QUALIFICATIONS" if "QUALIFICATIONS" in text.upper() else "PROJECTS" if "PROJECTS" in text.upper() else "")[0]
            education_entries = [e.strip()
                                for e in education_section.split('\n\n') if e.strip()]
            sections['education'] = education_entries[:5]  # Limit to 5 entries

        # Extract qualifications (basic implementation)
        if "QUALIFICATIONS" in text.upper() or "SKILLS" in text.upper():
            qual_keyword = "QUALIFICATIONS" if "QUALIFICATIONS" in text.upper() else "SKILLS"
            qual_section = text.upper().split(qual_keyword)[1].split(
                "PROJECTS" if "PROJECTS" in text.upper() else "EXPERIENCE" if "EXPERIENCE" in text.upper() else "")[0]
            qual_entries = [q.strip()
                            for q in qual_section.split('\n') if q.strip()]
            sections['qualifications'] = qual_entries[:10]  # Limit to 10 entries

        # Extract projects (basic implementation)
        if "PROJECTS" in text.upper():
            projects_section = text.upper().split("PROJECTS")[1].split(
                "EXPERIENCE" if "EXPERIENCE" in text.upper() else "REFERENCES" if "REFERENCES" in text.upper() else "")[0]
            project_entries = [p.strip()
                            for p in projects_section.split('\n\n') if p.strip()]
            sections['projects'] = project_entries[:5]  # Limit to 5 entries

        return sections