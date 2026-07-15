"""
ResumeAnalyzerNode - Migrate resume parsing to node-based architecture.
Wraps PersonalInfoExtractor for ApplicationState.
"""

from typing import Any, Dict, Optional
from pathlib import Path

from ..config import CONFIG
from ..extractor.extractor import PersonalInfoExtractor


class ResumeAnalyzerNode:
    """Node for analyzing resume PDFs and extracting personal information."""
    
    def __init__(self):
        self.extractor = None
        self.last_error = None
    
    def initialize(self):
        """Initialize extractor."""
        try:
            self.extractor = PersonalInfoExtractor(
                personal_info_dir=str(CONFIG.personal_info_dir)
            )
        except Exception as e:
            self.last_error = f"Failed to initialize extractor: {e}"
            raise
    
    def analyze(self, pdf_path: str, state: Optional[Any] = None) -> Dict[str, Any]:
        """
        Analyze resume PDF and extract personal information.
        
        Args:
            pdf_path: Path to resume PDF file
            state: Optional ApplicationState to update
            
        Returns:
            Dictionary with extracted data or error
        """
        if not self.extractor:
            self.initialize()
        
        try:
            # Verify PDF exists
            pdf_file = Path(pdf_path)
            if not pdf_file.exists():
                return {
                    "status": "failed",
                    "error": f"PDF file not found: {pdf_path}"
                }
            
            # Extract from resume
            result = self.extractor.extract_from_resume_pdf(pdf_path)
            
            if not result:
                return {
                    "status": "failed",
                    "error": "Resume parsing failed: please ensure PDF is copyable text (not scanned image) and model is configured"
                }
            
            # Update state if provided
            if state:
                state.resume_data = result
                state.add_log(f"Resume analysis: extracted {len(result.get('personal_info', {}))} fields")
            
            return {
                "status": "extracted",
                "data": result
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            
            error_msg = str(e)
            if state:
                state.errors.append(f"Resume analysis error: {error_msg}")
                state.add_log(f"Resume analysis failed: {error_msg}")
            
            return {
                "status": "failed",
                "error": error_msg
            }
    
    def consolidate(self, state: Optional[Any] = None) -> Dict[str, Any]:
        """
        Consolidate extracted information into unified profile.
        
        Args:
            state: Optional ApplicationState to update
            
        Returns:
            Dictionary with consolidated profile or error
        """
        if not self.extractor:
            self.initialize()
        
        try:
            profile = self.extractor.generate_unified_profile()
            
            if state:
                state.unified_profile = profile
                state.add_log(f"Profile consolidation: unified {len(profile)} fields")
            
            return {
                "status": "consolidated",
                "profile": profile
            }
            
        except Exception as e:
            error_msg = str(e)
            if state:
                state.errors.append(f"Profile consolidation error: {error_msg}")
                state.add_log(f"Profile consolidation failed: {error_msg}")
            
            return {
                "status": "failed",
                "error": error_msg
            }


# Global analyzer instance
_analyzer_instance = None


def get_analyzer() -> ResumeAnalyzerNode:
    """Get or create analyzer instance."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = ResumeAnalyzerNode()
        _analyzer_instance.initialize()
    return _analyzer_instance


def analyze_resume(pdf_path: str, state: Optional[Any] = None) -> Dict[str, Any]:
    """
    Public API to analyze resume.
    
    Args:
        pdf_path: Path to resume PDF
        state: Optional ApplicationState
        
    Returns:
        Analysis result with status and data/error
    """
    analyzer = get_analyzer()
    return analyzer.analyze(pdf_path, state)


def consolidate_profile(state: Optional[Any] = None) -> Dict[str, Any]:
    """
    Public API to consolidate profile.
    
    Args:
        state: Optional ApplicationState
        
    Returns:
        Consolidation result with status and profile/error
    """
    analyzer = get_analyzer()
    return analyzer.consolidate(state)
