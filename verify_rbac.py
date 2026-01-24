import unittest
from app import app

class RBACVerification(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret'
        self.client = app.test_client()

    # Helper to set session role
    def login_as(self, role):
        with self.client.session_transaction() as sess:
            sess['role'] = role
            sess['username'] = 'testuser'

    def test_home_customer_redirect(self):
        """Customer visiting / should redirect to /cart"""
        self.login_as('customer')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/cart' in response.location)

    def test_home_employee_access(self):
        """Employee visiting / should see home page"""
        self.login_as('employee')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_cart_customer_access(self):
        """Customer should access /cart"""
        self.login_as('customer')
        response = self.client.get('/cart')
        self.assertEqual(response.status_code, 200)

    def test_cart_superowner_access(self):
        """Superowner should access /cart"""
        self.login_as('superowner')
        response = self.client.get('/cart')
        self.assertEqual(response.status_code, 200)

    def test_cart_employee_redirect(self):
        """Employee visiting /cart should redirect to /dashboard"""
        self.login_as('employee')
        response = self.client.get('/cart')
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/dashboard' in response.location)

    def test_code_superowner_access(self):
        """Superowner should access /code"""
        self.login_as('superowner')
        response = self.client.get('/code')
        self.assertEqual(response.status_code, 200)

    def test_code_employee_deny(self):
        """Employee should NOT access /code (redirect to staff-login)"""
        self.login_as('employee')
        response = self.client.get('/code')
        self.assertEqual(response.status_code, 302)
        self.assertTrue('staff-login' in response.location)

if __name__ == '__main__':
    unittest.main()
