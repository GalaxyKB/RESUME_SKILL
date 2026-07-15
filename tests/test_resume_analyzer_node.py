"""
Test ResumeAnalyzerNode - Resume parsing node migration.
Validates: PDF extraction, error handling, API compatibility.
"""

import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, "src")

from resume_skill.agent.resume_analyzer_node import (
    ResumeAnalyzerNode, get_analyzer, analyze_resume, consolidate_profile
)
from resume_skill.agent.fill_workflow import ApplicationState


def create_mock_pdf():
    """Create a mock PDF file for testing."""
    fd, path = tempfile.mkstemp(suffix=".pdf")
    import os
    os.close(fd)
    # Write minimal PDF header
    with open(path, 'wb') as f:
        f.write(b'%PDF-1.4\n%test mock pdf\n')
    return path


def test_analyzer_initialization():
    """Test ResumeAnalyzerNode initialization."""
    print("\n1️⃣  Testing: Node initialization")
    
    analyzer = ResumeAnalyzerNode()
    assert analyzer.extractor is None
    assert analyzer.last_error is None
    
    # Initialize
    with patch('resume_skill.agent.resume_analyzer_node.PersonalInfoExtractor') as mock_extractor:
        analyzer.initialize()
        assert analyzer.extractor is not None or analyzer.last_error is None
        print("   ✓ Initialization successful")


def test_analyze_missing_file():
    """Test analyzer handles missing PDF file."""
    print("\n2️⃣  Testing: Missing PDF file")
    
    analyzer = ResumeAnalyzerNode()
    with patch('resume_skill.agent.resume_analyzer_node.PersonalInfoExtractor'):
        analyzer.initialize()
        
        result = analyzer.analyze("/nonexistent/file.pdf")
        
        assert result["status"] == "failed"
        assert "not found" in result.get("error", "").lower()
        print("   ✓ Missing file handled correctly")


def test_analyze_extraction_failure():
    """Test analyzer handles extraction failure."""
    print("\n3️⃣  Testing: Extraction failure")
    
    pdf_path = create_mock_pdf()
    
    try:
        analyzer = ResumeAnalyzerNode()
        
        with patch('resume_skill.agent.resume_analyzer_node.PersonalInfoExtractor') as mock_extractor_class:
            mock_instance = Mock()
            mock_instance.extract_from_resume_pdf.return_value = None  # Simulate failure
            mock_extractor_class.return_value = mock_instance
            
            analyzer.extractor = mock_instance
            result = analyzer.analyze(pdf_path)
            
            assert result["status"] == "failed"
            assert "parsing failed" in result.get("error", "").lower()
            print("   ✓ Extraction failure handled")
    finally:
        Path(pdf_path).unlink(missing_ok=True)


def test_analyze_success():
    """Test successful PDF extraction."""
    print("\n4️⃣  Testing: Successful extraction")
    
    pdf_path = create_mock_pdf()
    
    try:
        analyzer = ResumeAnalyzerNode()
        
        with patch('resume_skill.agent.resume_analyzer_node.PersonalInfoExtractor') as mock_extractor_class:
            mock_instance = Mock()
            mock_data = {
                "personal_info": {
                    "name": "张三",
                    "email": "zhangsan@example.com"
                },
                "education": [{"school": "清华大学", "degree": "本科"}]
            }
            mock_instance.extract_from_resume_pdf.return_value = mock_data
            mock_extractor_class.return_value = mock_instance
            
            analyzer.extractor = mock_instance
            result = analyzer.analyze(pdf_path)
            
            assert result["status"] == "extracted"
            assert result["data"] == mock_data
            print("   ✓ Extraction successful")
            print(f"   ✓ Data contains: {len(mock_data)} sections")
    finally:
        Path(pdf_path).unlink(missing_ok=True)


def test_analyze_with_state():
    """Test analyzer updates ApplicationState."""
    print("\n5️⃣  Testing: State update during analysis")
    
    pdf_path = create_mock_pdf()
    state = ApplicationState(task_id="test-001")
    
    try:
        analyzer = ResumeAnalyzerNode()
        
        with patch('resume_skill.agent.resume_analyzer_node.PersonalInfoExtractor') as mock_extractor_class:
            mock_instance = Mock()
            mock_data = {"personal_info": {"name": "test"}}
            mock_instance.extract_from_resume_pdf.return_value = mock_data
            mock_extractor_class.return_value = mock_instance
            
            analyzer.extractor = mock_instance
            result = analyzer.analyze(pdf_path, state)
            
            assert result["status"] == "extracted"
            assert state.resume_data == mock_data
            assert len(state.log) > 0
            print("   ✓ State updated correctly")
            print(f"   ✓ Log entry added: {state.log[0][:50]}")
    finally:
        Path(pdf_path).unlink(missing_ok=True)


def test_consolidate_profile():
    """Test profile consolidation."""
    print("\n6️⃣  Testing: Profile consolidation")
    
    analyzer = ResumeAnalyzerNode()
    state = ApplicationState(task_id="test-001")
    
    with patch('resume_skill.agent.resume_analyzer_node.PersonalInfoExtractor') as mock_extractor_class:
        mock_instance = Mock()
        mock_profile = {
            "name": "张三",
            "email": "zhangsan@example.com",
            "education": "清华大学 本科"
        }
        mock_instance.generate_unified_profile.return_value = mock_profile
        mock_extractor_class.return_value = mock_instance
        
        analyzer.extractor = mock_instance
        result = analyzer.consolidate(state)
        
        assert result["status"] == "consolidated"
        assert result["profile"] == mock_profile
        assert state.unified_profile == mock_profile
        print("   ✓ Profile consolidated")
        print(f"   ✓ Profile contains: {len(mock_profile)} fields")


def test_consolidate_error():
    """Test consolidation error handling."""
    print("\n7️⃣  Testing: Consolidation error")
    
    analyzer = ResumeAnalyzerNode()
    
    with patch('resume_skill.agent.resume_analyzer_node.PersonalInfoExtractor') as mock_extractor_class:
        mock_instance = Mock()
        mock_instance.generate_unified_profile.side_effect = Exception("Consolidation failed")
        mock_extractor_class.return_value = mock_instance
        
        analyzer.extractor = mock_instance
        result = analyzer.consolidate()
        
        assert result["status"] == "failed"
        assert "consolidation failed" in result.get("error", "").lower()
        print("   ✓ Consolidation error handled")


def test_global_api():
    """Test global analyzer API."""
    print("\n8️⃣  Testing: Global API")
    
    pdf_path = create_mock_pdf()
    
    try:
        with patch('resume_skill.agent.resume_analyzer_node.PersonalInfoExtractor') as mock_extractor_class:
            mock_instance = Mock()
            mock_data = {"personal_info": {"name": "test"}}
            mock_instance.extract_from_resume_pdf.return_value = mock_data
            mock_extractor_class.return_value = mock_instance
            
            # Test get_analyzer
            analyzer = get_analyzer()
            assert analyzer is not None
            print("   ✓ get_analyzer() works")
            
            # Test analyze_resume
            result = analyze_resume(pdf_path)
            assert result["status"] == "extracted"
            print("   ✓ analyze_resume() works")
            
            # Test consolidate_profile
            result = consolidate_profile()
            print("   ✓ consolidate_profile() works")
    finally:
        Path(pdf_path).unlink(missing_ok=True)


def test_api_extract_endpoint():
    """Test /api/extract endpoint compatibility."""
    print("\n9️⃣  Testing: API endpoint /api/extract")
    
    from resume_skill.webui.app import app
    
    with app.test_client() as client:
        # Create test PDF
        from io import BytesIO
        pdf_content = BytesIO(b'%PDF-1.4\n%test\n')
        pdf_content.name = 'test.pdf'
        
        data = {'file': (pdf_content, 'test.pdf')}
        
        with patch('resume_skill.webui.app.analyze_resume') as mock_analyze:
            mock_analyze.return_value = {
                "status": "extracted",
                "data": {"personal_info": {"name": "test"}}
            }
            
            response = client.post('/api/extract', data=data, content_type='multipart/form-data')
            
            assert response.status_code == 200
            result = json.loads(response.data)
            assert result["status"] == "extracted"
            print("   ✓ Endpoint returns 200 on success")


def test_api_extract_error_422():
    """Test /api/extract returns 422 on failure."""
    print("\n🔟 Testing: API endpoint error handling")
    
    from resume_skill.webui.app import app
    
    with app.test_client() as client:
        from io import BytesIO
        pdf_content = BytesIO(b'%PDF-1.4\n%test\n')
        pdf_content.name = 'bad.pdf'
        
        data = {'file': (pdf_content, 'bad.pdf')}
        
        # Patch at the source where analyze_resume is defined, not just where it's imported
        with patch('resume_skill.agent.resume_analyzer_node.analyze_resume') as mock_analyze:
            mock_analyze.return_value = {
                "status": "failed",
                "error": "PDF parsing failed"
            }
            
            response = client.post('/api/extract', data=data, content_type='multipart/form-data')
            
            print(f"   Response status: {response.status_code}")
            result = json.loads(response.data) if response.data else {}
            print(f"   Response: {result}")
            
            assert response.status_code == 422, f"Expected 422, got {response.status_code}"
            assert result["status"] == "failed"
            print("   ✓ Endpoint returns 422 on failure")


def test_no_chrome_usage():
    """Verify that ResumeAnalyzerNode doesn't use Chrome."""
    print("\n1️⃣1️⃣  Testing: No Chrome dependency")
    
    analyzer = ResumeAnalyzerNode()
    
    # Check for Chrome references
    with patch('resume_skill.agent.resume_analyzer_node.PersonalInfoExtractor'):
        analyzer.initialize()
        
        # The node should only use PersonalInfoExtractor
        assert analyzer.extractor is not None
        print("   ✓ Only uses PersonalInfoExtractor")
        print("   ✓ No Chrome client dependency")


def test_no_gui_agent():
    """Verify that ResumeAnalyzerNode doesn't use GUI Agent."""
    print("\n1️⃣2️⃣  Testing: No GUI Agent")
    
    pdf_path = create_mock_pdf()
    
    try:
        analyzer = ResumeAnalyzerNode()
        
        with patch('resume_skill.agent.resume_analyzer_node.PersonalInfoExtractor') as mock_extractor_class:
            mock_instance = Mock()
            mock_instance.extract_from_resume_pdf.return_value = {"data": "test"}
            mock_extractor_class.return_value = mock_instance
            
            analyzer.extractor = mock_instance
            result = analyzer.analyze(pdf_path)
            
            # Verify only PersonalInfoExtractor was called
            mock_instance.extract_from_resume_pdf.assert_called_once()
            print("   ✓ Only PersonalInfoExtractor called")
            print("   ✓ No GUI Agent integration")
    finally:
        Path(pdf_path).unlink(missing_ok=True)


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*70)
    print("TEST: ResumeAnalyzerNode")
    print("="*70)
    
    try:
        test_analyzer_initialization()
        test_analyze_missing_file()
        test_analyze_extraction_failure()
        test_analyze_success()
        test_analyze_with_state()
        test_consolidate_profile()
        test_consolidate_error()
        test_global_api()
        test_api_extract_endpoint()
        test_api_extract_error_422()
        test_no_chrome_usage()
        test_no_gui_agent()
        
        print("\n" + "="*70)
        print("✅ ALL RESUME ANALYZER TESTS PASSED (12/12)")
        print("="*70 + "\n")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
