import datetime
import requests
import uuid
from collections import OrderedDict
from typing import Any, Dict

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from pretix.base.payment import BasePaymentProvider
from pretix.base.cache import ObjectRelatedCache

class ScbPartnerApi():
    """
    Provide convenience wrapper around SCB partner API convention.
    """

    class BussinessError(RuntimeError):
        def __init__(self, code, description):
            super().__init__('Bussiness error %d: %s' % (code, description))
            self.code = code
            self.description = description

    access_token: Dict[str, Any]

    def __init__(self, base_url: str, app_key: str, app_secret: str, cache: ObjectRelatedCache):
        self.base_url = base_url
        self.v1_url = base_url + '/v1'

        self.app_key = app_key
        self.app_secret = app_secret
        self.cache = cache

        self.access_token = None

    def post(self, url: str, json: Dict[str, Any], skip_authz=False):
        """
            POST to the URL, handle things common to SCB API.
            skip_authz is used by get_authz_header() itself.
            Returns 'data' field directly
        """
        headers = {
            'resourceOwnerId': self.app_key,
            'requestUId': str(uuid.uuid4()), # Yet to find its purpose.
            'accept-language': 'EN'
        }
        if not skip_authz:
            headers['authorization'] = self.get_authz_header()

        response = requests.post(url=url, json=json, headers=headers).json()
        status = response['status']
        if status['code'] != 1000:
            raise ScbPartnerApi.BussinessError(status['code'], status['description'])

        return response['data']

    def is_access_token_expired(self):
        now = timezone.now()
        expiresAt = datetime.datetime.fromtimestamp(self.access_token['expiresAt'])
        # Expire the token 60 seconds early, so that we don't use expired token
        return expiresAt - datetime.timedelta(seconds=60) <= now

    def get_authz_header(self):
        if self.access_token is None:
            self.access_token = self.cache.get('scb_access_token')

        if self.access_token is None or self.is_access_token_expired():
            self.access_token = self.post(
                url=self.v1_url + '/oauth/token',
                json={
                    'applicationKey': self.app_key,
                    'applicationSecret': self.app_secret,
                },
                skip_authz=True
            )
            self.cache.set('scb_access_token', self.access_token, timeout=self.access_token['expiresIn'])

        return '%s %s' % (self.access_token['tokenType'], self.access_token['accessToken'])


class PromptPayScbPaymentProvider(BasePaymentProvider):
    identifier = 'promptpay_scb'
    verbose_name = 'Thai PromptPay QR via SCB API'
    public_name = 'PromptPay QR (โมบายแบงก์กิ้ง)'

    @property
    def settings_form_fields(self):
        return OrderedDict(
            list(super().settings_form_fields.items()) + [
                # I'm not sure if the production endpoint is fixed.
                ('api_url', forms.CharField(
                    widget=forms.TextInput,
                    label=_('SCB partner API endpoint'),
                    help_text=_('Starts with https://. Do not include /v1/ in the URL.'),
                    required=True,
                    initial='https://api-sandbox.partners.scb/partners/sandbox',
                )),
                ('application_key', forms.CharField(
                    widget=forms.TextInput,
                    label=_('Application key'),
                    help_text=_('Obtained from the partner portal.'),
                    required=True,
                )),
                ('application_secret', forms.CharField(
                    widget=forms.TextInput,
                    label=_('Application secret'),
                    required=True,
                )),
                ('pp_id', forms.CharField(
                    widget=forms.TextInput,
                    label=_('Biller ID'),
                    required=True,
                )),
                ('ref1_prefix', forms.RegexField(
                    widget=forms.TextInput,
                    label=_('Reference 1 prefix'),
                    help_text=_('Will be prepended in front of the event slug. '
                                'English capital letter and number only. '
                                'Note that the reference 2 will always be Pretix\'s payment ID.'),
                    required=False,
                    regex='[A-Z0-9]*',
                    initial='PRETIX',
                )),
                ('ref3_prefix', forms.RegexField(
                    widget=forms.TextInput,
                    label=_('Reference 3 prefix'),
                    help_text=_('Have to match the reference 3 prefix configured as plugin\'s callback.'),
                    required=True,
                    regex='[A-Z0-9]*',
                )),
            ]
        )

    def is_allowed(self, request, total):
        return super().is_allowed(request, total) and self.event.currency == 'THB'

    def payment_is_valid_session(self, request):
        # We do not store any session info
        return True

    def payment_form_render(self, request, total):
        return _('''
ชำระเงินผ่านระบบ PromptPay โดยทำการแสกน QR code ด้วยแอปพลิเคชันโมบายแบงก์กิ้งของธนาคารใดก็ได้เพื่อชำระเงิน
''')

    def checkout_confirm_render(self, request):
        return _('''
ระบบจะแสดง QR code ในหน้าถัดไป โปรดชำระเงินภายใน 10 นาที มิฉะนั้น ท่านจะต้องเริ่มการชำระเงินอีกครั้ง
''')
