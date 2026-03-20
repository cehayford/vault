from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
import pyotp
from userauth.models import EmailVerification, SecurityLog
from userauth.views import _send_phone_otp_email_sync


User = get_user_model()


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class AuthFlowIntegrationTests(TestCase):
    def setUp(self):
        self.password = "StrongPass123!"
        self.user = User.objects.create_user(
            email="flow.user@example.com",
            first_name="Flow",
            last_name="User",
            password=self.password,
            phone_number="+15555550123",
            is_active=True,
            is_verified=True,
            data_consent=True,
        )
        self.client.login(username=self.user.email, password=self.password)

    @override_settings(DEBUG=True)
    def test_send_phone_otp_renders_phone_verify_and_logs_event(self):
        with patch("userauth.views._send_phone_otp_email_sync", return_value=True) as mock_email, patch(
            "voting.tasks.send_phone_otp"
        ) as mock_task:
            response = self.client.get(reverse("userauth:send_phone_otp"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "userauth/phone_verify.html")
        self.assertContains(response, "OTP is sent to your phone and your email")
        self.assertContains(response, "Verify code")
        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.phone_otp))
        self.assertTrue(
            SecurityLog.objects.filter(
                user=self.user,
                action_type="phone_otp_sent",
            ).exists()
        )
        mock_email.assert_called_once_with(self.user.email, self.user.phone_otp)
        self.assertTrue(mock_task.apply.called)

    def test_phone_verify_valid_code_marks_phone_verified(self):
        self.user.phone_otp = "123456"
        self.user.phone_otp_created_at = timezone.now()
        self.user.save(update_fields=["phone_otp", "phone_otp_created_at"])
        response = self.client.post(
            reverse("userauth:phone_verify"),
            {"otp_code": "123 456"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("voting:dashboard"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.phone_verified)
        self.assertIsNone(self.user.phone_otp)
        self.assertTrue(
            SecurityLog.objects.filter(
                user=self.user,
                action_type="phone_verified",
                success=True,
            ).exists()
        )

    def test_debug_code_stays_visible_until_phone_is_verified(self):
        session = self.client.session
        session["dev_otp_show"] = "777888"
        session.save()
        first = self.client.get(reverse("userauth:phone_verify"))
        second = self.client.get(reverse("userauth:phone_verify"))
        self.assertContains(first, "777888")
        self.assertContains(second, "777888")

    def test_successful_phone_verify_clears_debug_code_session(self):
        self.user.phone_otp = "121212"
        self.user.phone_otp_created_at = timezone.now()
        self.user.save(update_fields=["phone_otp", "phone_otp_created_at"])
        session = self.client.session
        session["dev_otp_show"] = "121212"
        session.save()
        response = self.client.post(reverse("userauth:phone_verify"), {"otp_code": "121212"})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("dev_otp_show", self.client.session)

    def test_email_verification_code_activates_account(self):
        unverified = User.objects.create_user(
            email="verify.user@example.com",
            first_name="Verify",
            last_name="User",
            password="VerifyPass123!",
            is_active=False,
            is_verified=False,
            data_consent=True,
        )
        EmailVerification.objects.create(
            user=unverified,
            code="654321",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        response = self.client.post(
            reverse("userauth:email_verification"),
            {"code": "654321"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("voting:dashboard"))
        unverified.refresh_from_db()
        self.assertTrue(unverified.is_active)
        self.assertTrue(unverified.is_verified)


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class MFASetupFlowTests(TestCase):
    def setUp(self):
        self.password = "MfaPass123!"
        self.user = User.objects.create_user(
            email="mfa.setup@example.com",
            first_name="Mfa",
            last_name="Setup",
            password=self.password,
            is_active=True,
            is_verified=True,
            data_consent=True,
        )
        self.client.login(username=self.user.email, password=self.password)

    def test_setup_accepts_valid_authenticator_code_before_mfa_enabled(self):
        response = self.client.get(reverse("userauth:mfa_setup"))
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.mfa_secret)
        self.assertFalse(self.user.mfa_enabled)
        token = pyotp.TOTP(self.user.mfa_secret).now()
        response = self.client.post(reverse("userauth:mfa_setup"), {"token": token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("voting:dashboard"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.mfa_enabled)
        self.assertTrue(
            SecurityLog.objects.filter(user=self.user, action_type="mfa_enabled", success=True).exists()
        )

    def test_setup_accepts_token_with_space_separator(self):
        self.client.get(reverse("userauth:mfa_setup"))
        self.user.refresh_from_db()
        token = pyotp.TOTP(self.user.mfa_secret).now()
        spaced = f"{token[:3]} {token[3:]}"
        response = self.client.post(reverse("userauth:mfa_setup"), {"token": spaced})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("voting:dashboard"))


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class AuthFlowSecurityTests(TestCase):
    def setUp(self):
        self.password = "SecurePass123!"
        self.user_with_phone = User.objects.create_user(
            email="secure.user@example.com",
            first_name="Secure",
            last_name="User",
            password=self.password,
            phone_number="+15555550124",
            is_active=True,
            is_verified=True,
            data_consent=True,
        )
        self.user_without_phone = User.objects.create_user(
            email="nophone.user@example.com",
            first_name="No",
            last_name="Phone",
            password=self.password,
            is_active=True,
            is_verified=True,
            data_consent=True,
        )

    def test_send_phone_otp_requires_authentication(self):
        response = self.client.get(reverse("userauth:send_phone_otp"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("userauth:login"), response.url)

    def test_send_phone_otp_without_phone_redirects_to_profile(self):
        self.client.login(username=self.user_without_phone.email, password=self.password)
        response = self.client.get(reverse("userauth:send_phone_otp"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "userauth/profile.html")
        self.assertContains(response, "No phone number on your account")

    def test_invalid_otp_does_not_verify_phone(self):
        self.client.login(username=self.user_with_phone.email, password=self.password)
        self.user_with_phone.phone_otp = "111111"
        self.user_with_phone.phone_otp_created_at = timezone.now()
        self.user_with_phone.save(update_fields=["phone_otp", "phone_otp_created_at"])
        response = self.client.post(
            reverse("userauth:phone_verify"),
            {"otp_code": "222222"},
            follow=True,
        )
        self.user_with_phone.refresh_from_db()
        self.assertFalse(self.user_with_phone.phone_verified)
        self.assertContains(response, "Invalid or expired code")


class OTPEmailUnitTests(SimpleTestCase):
    @patch("userauth.views.send_mail")
    def test_send_phone_otp_email_returns_false_for_invalid_email(self, mock_send_mail):
        sent = _send_phone_otp_email_sync("", "123456")
        self.assertFalse(sent)
        mock_send_mail.assert_not_called()

    @patch("userauth.views.send_mail", return_value=1)
    def test_send_phone_otp_email_returns_true_on_success(self, mock_send_mail):
        sent = _send_phone_otp_email_sync("valid@example.com", "123456")
        self.assertTrue(sent)
        mock_send_mail.assert_called_once()

    @patch("userauth.views.send_mail", side_effect=Exception("mail down"))
    def test_send_phone_otp_email_returns_false_on_exception(self, mock_send_mail):
        sent = _send_phone_otp_email_sync("valid@example.com", "123456")
        self.assertFalse(sent)
        mock_send_mail.assert_called_once()
