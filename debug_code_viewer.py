import unittest
from app import app
import os

class CodeViewerTest(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret'
        self.client = app.test_client()
        # Ensure superowner exists or we mock session
        
    def login_as_superowner(self):
        with self.client.session_transaction() as sess:
            sess['role'] = 'superowner'
            sess['username'] = 'superowner'

    def test_list_files(self):
        self.login_as_superowner()
        response = self.client.get('/code')
        self.assertEqual(response.status_code, 200, "Failed to load /code page")
        self.assertIn(b'app.py', response.data, "app.py not listed in file list")

    def test_view_file(self):
        self.login_as_superowner()
        # Try to view app.py
        response = self.client.get('/code?file=app.py')
        self.assertEqual(response.status_code, 200, "Failed to load /code?file=app.py")
        self.assertIn(b'Flask', response.data, "Content of app.py not shown (looking for 'Flask')")

    def test_view_subdir_file(self):
        self.login_as_superowner()
        # Try to view templates/cart.html
        # Note: on Windows join might use backslash, url might need to handle it.
        # Let's see how the app lists it.
        # The app uses os.path.relpath which uses os.sep.
        # On Windows this will be templates\cart.html
        
        filename = os.path.join("templates", "cart.html")
        print(f"Requesting file: {filename}")
        response = self.client.get(f'/code?file={filename}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'html', response.data)

if __name__ == '__main__':
    unittest.main()
