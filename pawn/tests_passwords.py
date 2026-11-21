from django.contrib.auth.hashers import check_password
from django.core.management import call_command
from django.test import TestCase

from .models import Customer, User


class PasswordAndPinTests(TestCase):
    PW = "OnlyPawns#2026"

    def setUp(self):
        call_command("seed", verbosity=0)
        self.cashier = User.objects.get(username="cashier")
        self.maria = Customer.objects.get(last_name="Santos").user

    def staff_login(self, name="cashier", pw=None):
        self.client.logout()
        return self.client.login(username=name, password=pw or self.PW)

    # ---- staff change own password
    def test_staff_can_change_own_password_and_stay_signed_in(self):
        self.staff_login()
        r = self.client.post("/staff/password/", {"current": self.PW, "new": "Brand-new-pass-9", "confirm": "Brand-new-pass-9"})
        self.assertEqual(r.status_code, 302)
        self.cashier.refresh_from_db()
        self.assertTrue(self.cashier.check_password("Brand-new-pass-9"))
        self.assertEqual(self.client.get("/staff/").status_code, 200)     # session survived the change

    def test_every_staff_role_has_the_page(self):
        for name in ("admin", "cashier", "appraiser"):
            self.staff_login(name)
            self.assertEqual(self.client.get("/staff/password/").status_code, 200, name)

    def test_bad_password_changes_are_refused(self):
        self.staff_login()
        cases = [({"current": "wrong", "new": "Brand-new-pass-9", "confirm": "Brand-new-pass-9"}, "current"),
                 ({"current": self.PW, "new": "Brand-new-pass-9", "confirm": "different-one-1"}, "match"),
                 ({"current": self.PW, "new": "short", "confirm": "short"}, "short"),
                 ({"current": self.PW, "new": self.PW, "confirm": self.PW}, "same")]
        for data, label in cases:
            self.client.post("/staff/password/", data)
            self.cashier.refresh_from_db()
            self.assertTrue(self.cashier.check_password(self.PW), label)

    def test_repeated_wrong_current_password_locks_the_account(self):
        self.staff_login()
        for _ in range(5):
            self.client.post("/staff/password/", {"current": "nope", "new": "Brand-new-pass-9", "confirm": "Brand-new-pass-9"})
        self.cashier.refresh_from_db()
        self.assertTrue(self.cashier.is_locked())

    # ---- administrator resets a staff password
    def test_admin_reset_gives_a_one_time_password_and_forces_a_change(self):
        self.staff_login("admin")
        emp = self.cashier.employee
        r = self.client.post(f"/staff/admin/employees/{emp.pk}/reset-password/", follow=True)
        self.assertEqual(r.status_code, 200)
        temp = r.context["secret"]
        self.assertGreaterEqual(len(temp), 10)
        self.assertEqual(self.client.get("/staff/credential/").status_code, 302)      # shown once only
        self.cashier.refresh_from_db()
        self.assertTrue(self.cashier.must_change_password)
        self.assertFalse(self.cashier.check_password(self.PW))
        # the cashier signs in with the temporary password but is held on the change page
        self.assertTrue(self.staff_login("cashier", temp))
        self.assertEqual(self.client.get("/staff/").status_code, 302)
        self.assertEqual(self.client.get("/staff/").url, "/staff/password/")
        self.assertEqual(self.client.get("/staff/password/").status_code, 200)
        self.client.post("/staff/password/", {"current": temp, "new": "My-own-pass-77", "confirm": "My-own-pass-77"})
        self.assertEqual(self.client.get("/staff/").status_code, 200)
        self.cashier.refresh_from_db()
        self.assertFalse(self.cashier.must_change_password)

    def test_only_admin_can_reset_staff_passwords_and_not_their_own(self):
        emp = self.cashier.employee
        self.staff_login("cashier")
        self.client.post(f"/staff/admin/employees/{emp.pk}/reset-password/")
        self.cashier.refresh_from_db()
        self.assertTrue(self.cashier.check_password(self.PW))
        self.staff_login("admin")
        admin = User.objects.get(username="admin")
        self.client.post(f"/staff/admin/employees/{admin.employee.pk}/reset-password/")
        admin.refresh_from_db()
        self.assertTrue(admin.check_password(self.PW))

    # ---- customers: change PIN, and counter reset
    def test_customer_can_change_pin(self):
        self.client.force_login(self.maria)
        self.assertEqual(self.client.get("/app/pin/").status_code, 200)
        bad = [("111111", "222222", "222222"), ("123456", "123456", "123456"), ("123456", "999999", "888888"),
               ("123456", "111111", "111111"), ("123456", "12ab56", "12ab56")]
        for cur, new, conf in bad:
            self.client.post("/app/pin/", {"current": cur, "pin": new, "pin2": conf})
        self.maria.refresh_from_db()
        self.assertTrue(check_password("123456", self.maria.pin_hash))
        r = self.client.post("/app/pin/", {"current": "123456", "pin": "654321", "pin2": "654321"})
        self.assertEqual(r.status_code, 302)
        self.maria.refresh_from_db()
        self.assertTrue(check_password("654321", self.maria.pin_hash))

    def test_counter_reset_pin_forces_customer_to_choose_a_new_one(self):
        self.staff_login("cashier")
        cust = Customer.objects.get(last_name="Santos")
        r = self.client.post(f"/staff/customers/{cust.pk}/reset-pin/", follow=True)
        temp = r.context["secret"]
        self.assertEqual(len(temp), 6)
        self.assertTrue(temp.isdigit())
        self.client.logout()
        # sign in the way the app does it: Google identity first, then the PIN
        self.client.post("/app/login/", {"step": "google", "email": "maria.santos@example.com"})
        self.client.post("/app/login/", {"step": "pin", "pin": temp})
        home = self.client.get("/app/home/")
        self.assertEqual((home.status_code, home.url), (302, "/app/pin/"))
        self.client.post("/app/pin/", {"current": temp, "pin": "482913", "pin2": "482913"})
        self.assertEqual(self.client.get("/app/home/").status_code, 200)
        self.maria.refresh_from_db()
        self.assertFalse(self.maria.must_change_password)

    def test_appraiser_cannot_reset_a_customer_pin(self):
        self.staff_login("appraiser")
        cust = Customer.objects.get(last_name="Santos")
        self.client.post(f"/staff/customers/{cust.pk}/reset-pin/")
        self.maria.refresh_from_db()
        self.assertTrue(check_password("123456", self.maria.pin_hash))
