"""
Verify that Step 1 (resume extraction API) still works.
"""
import sys
import json

sys.path.insert(0, "src")

from resume_skill.webui.app import app


def test_step1_extract_api_exists():
    """Test that /api/extract endpoint still exists and works."""
    with app.test_client() as client:
        # Try posting without a file (should fail gracefully)
        response = client.post('/api/extract')
        
        # Should return 400 for missing file
        assert response.status_code == 400, f"Expected 400 for missing file, got {response.status_code}"
        data = json.loads(response.data)
        assert 'error' in data, "Should return error message"
        print("✓ /api/extract returns 400 for missing file")


def test_profile_api():
    """Test that profile-related APIs still work."""
    with app.test_client() as client:
        # Test /api/profile GET
        response = client.get('/api/profile')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'exists' in data
        print("✓ /api/profile GET works")
        
        # Test /api/profile/template GET
        response = client.get('/api/profile/template')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'exists' in data
        print("✓ /api/profile/template GET works")
        
        # Test /api/preferences GET
        response = client.get('/api/preferences')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'personal_info' in data
        print("✓ /api/preferences GET works")


def test_index_page():
    """Test that index page still renders."""
    with app.test_client() as client:
        response = client.get('/')
        assert response.status_code == 200
        html = response.data.decode()
        assert 'RESUME_SKILL' in html
        assert 'v2.4' in html
        print("✓ Index page renders correctly")


if __name__ == '__main__':
    print("\n=== Testing Step 1 Backward Compatibility ===\n")
    
    try:
        test_step1_extract_api_exists()
        test_profile_api()
        test_index_page()
        
        print("\n✓ All backward compatibility tests passed!\n")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
