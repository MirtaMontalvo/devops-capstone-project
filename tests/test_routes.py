"""
Account API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
"""
import os
import logging
from unittest import TestCase
from tests.factories import AccountFactory
from service.common import status  # HTTP Status Codes
from service.models import db, Account, init_db
from service.routes import app
from service import talisman

DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)

BASE_URL = "/accounts"
HTTPS_ENVIRON = {'wsgi.url_scheme': 'https'}


######################################################################
#  T E S T   C A S E S
######################################################################
class TestAccountService(TestCase):
    """Account Service Tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)

        talisman.force_https = False

    @classmethod
    def tearDownClass(cls):
        """Runs once before test suite"""

    def setUp(self):
        """Runs before each test"""
        db.session.query(Account).delete()  # clean up the last tests
        db.session.commit()

        self.client = app.test_client()

    def tearDown(self):
        """Runs once after each test case"""
        db.session.remove()

    ######################################################################
    #  H E L P E R   M E T H O D S
    ######################################################################

    def _create_accounts(self, count):
        """Factory method to create accounts in bulk"""
        accounts = []
        for _ in range(count):
            account = AccountFactory()
            response = self.client.post(BASE_URL, json=account.serialize())
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                "Could not create test Account",
            )
            new_account = response.get_json()
            account.id = new_account["id"]
            accounts.append(account)
        return accounts

    ######################################################################
    #  A C C O U N T   T E S T   C A S E S
    ######################################################################

    def test_index(self):
        """It should get 200_OK from the Home Page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health(self):
        """It should be healthy"""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "OK")

    def test_create_account(self):
        """It should Create a new Account"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_account = response.get_json()
        self.assertEqual(new_account["name"], account.name)
        self.assertEqual(new_account["email"], account.email)
        self.assertEqual(new_account["address"], account.address)
        self.assertEqual(new_account["phone_number"], account.phone_number)
        self.assertEqual(new_account["date_joined"], str(account.date_joined))

    def test_bad_request(self):
        """It should not Create an Account when sending the wrong data"""
        response = self.client.post(BASE_URL, json={"name": "not enough data"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unsupported_media_type(self):
        """It should not Create an Account when sending the wrong media type"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="test/html"
        )
        expected_status = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        self.assertEqual(response.status_code, expected_status)

    # ADD YOUR TEST CASES HERE ...

    # Get single account test cases
    def test_get_account(self):
        """It should Get a single Account"""
        account = self._create_accounts(1)[0]
        resp = self.client.get(
            f"{BASE_URL}/{account.id}", content_type="application/json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        self.assertEqual(data["name"], account.name)

    def test_get_account_not_found(self):
        """It should not Get an account when the id is not found"""
        resp = self.client.get(
            f"{BASE_URL}/9999", content_type="application/json"
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # Update account test cases
    def test_update_account(self):
        """It should Update an existing Account"""
        # Create an Account to update
        test_account = AccountFactory()
        resp = self.client.post(BASE_URL, json=test_account.serialize())
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # Get the initial state of the account
        initial_account = resp.get_json()

        # Update the account
        new_account = resp.get_json()
        new_account["name"] = "Something New"
        update_url = f"{BASE_URL}/{new_account['id']}"
        resp = self.client.put(update_url, json=new_account)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Get the updated state of the account
        resp = self.client.get(update_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        updated_account = resp.get_json()

        # Check if the initial name is different from the updated name
        self.assertNotEqual(initial_account["name"], updated_account["name"])
        # Check if the updated name matches what we set it to
        self.assertEqual(updated_account["name"], "Something New")

    def test_update_account_with_duplicate_email(self):
        """
        It should not update an account's email if that email is
        already associated with another account
        """

        # Create two distinct accounts
        account1 = self._create_accounts(1)[0]
        account2 = self._create_accounts(1)[0]

        # Update account1 to have the email of account2
        update_data = {"email": account2.email}
        response_url = f"{BASE_URL}/{account1.id}"
        response = self.client.put(response_url, json=update_data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_bad_update_request(self):
        """It should not Update an Account when sending the wrong data"""
        response = self.client.post(BASE_URL, json={"name": "not enough data"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_account_not_found(self):
        """It should not Update an account that is not found"""
        resp = self.client.put(f"{BASE_URL}/9999")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_method_not_allowed_update(self):
        """It should not allow an illegal Update method call"""
        response = self.client.put(BASE_URL)
        expected_status = status.HTTP_405_METHOD_NOT_ALLOWED
        self.assertEqual(response.status_code, expected_status)

    # Delete account test cases
    def test_delete_account(self):
        """It should Delete an Account"""
        account = self._create_accounts(1)[0]
        resp = self.client.delete(f"{BASE_URL}/{account.id}")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_account_not_found(self):
        """There is no Delete operation if the account does not exist"""
        resp = self.client.delete(f"{BASE_URL}/0")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_method_not_allowed_delete(self):
        """It should not allow an illegal Delete method call"""
        response = self.client.delete(BASE_URL)
        expected_status = status.HTTP_405_METHOD_NOT_ALLOWED
        self.assertEqual(response.status_code, expected_status)

    # Get List of accounts test cases
    def test_get_account_list(self):
        """It should Get a List of accounts"""
        self._create_accounts(5)
        resp = self.client.get(BASE_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        self.assertEqual(len(data), 5)

    def test_empty_accounts_list(self):
        """It should return an empty List when there are no accounts"""

        # Ensure that no accounts are present to begin with.
        # This depends on the setup of your testing environment.
        # The following line deletes all accounts for a clean slate.
        db.session.query(Account).delete()
        db.session.commit()

        resp = self.client.get(BASE_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.get_json()
        self.assertEqual(len(data), 0)

    ######################################################################
    #  S E C U R I T Y  T E S T   C A S E S
    ######################################################################

    def test_security_headers(self):
        """It should return security headers"""
        response = self.client.get('/', environ_overrides=HTTPS_ENVIRON)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        headers = {
            'X-Frame-Options': 'SAMEORIGIN',
            'X-XSS-Protection': '1; mode=block',
            'X-Content-Type-Options': 'nosniff',
            'Content-Security-Policy': (
                "default-src 'self'; object-src 'none'"
            ),
            'Referrer-Policy': 'strict-origin-when-cross-origin'
        }
        for key, value in headers.items():
            self.assertEqual(response.headers.get(key), value)

    def test_cors_security(self):
        """It should return a CORS header"""
        response = self.client.get('/', environ_overrides=HTTPS_ENVIRON)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check for the CORS header
        cors_header = 'Access-Control-Allow-Origin'
        self.assertEqual(response.headers.get(cors_header), '*')

    def test_acct_to_string(self):
        """Account repr should return the account name and id"""
        account = self._create_accounts(1)[0]
        string_test = repr(account)
        expected_string = f'<Account {account.name} id=[{account.id}]>'
        self.assertEqual(string_test, expected_string)
