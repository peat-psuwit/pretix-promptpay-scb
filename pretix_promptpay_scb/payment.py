import datetime
import logging
import re
import requests
import string
import uuid
from collections import OrderedDict
from decimal import Decimal
from typing import Any, Dict

from django import forms
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _

from pretix.base.models.orders import OrderPayment
from pretix.base.payment import BasePaymentProvider, PaymentException
from pretix.base.cache import ObjectRelatedCache
from pretix.multidomain.urlreverse import eventreverse, build_absolute_uri

logger = logging.getLogger('pretix_promptpay_scb')

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

    def qrcode_create_biller(self, amount: Decimal, ppId: str, ref1: str, ref2: str, ref3: str):
        return self.post(url=self.v1_url + '/payment/qrcode/create', json={
            'qrType': 'PP',
            'ppType': 'BILLERID',
            'ppId': ppId,
            'ref1': ref1,
            'ref2': ref2,
            'ref3': ref3,
            'amount': str(amount),
        })


class PromptPayScbPaymentProvider(BasePaymentProvider):
    identifier = 'promptpay_scb'
    verbose_name = 'Thai PromptPay QR via SCB API'
    public_name = 'PromptPay QR (โมบายแบงก์กิ้ง)'

    @property
    def settings_form_fields(self):
        return OrderedDict(
            list(super().settings_form_fields.items()) + [
                # I'm not sure if the production endpoint is fixed.
                ('api_url', forms.URLField(
                    label=_('SCB partner API endpoint'),
                    help_text=_('Starts with https://. Do not include /v1 in the URL. '
                                'Trailing slash will be removed.'),
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
                ('ref3_prefix', forms.RegexField(
                    widget=forms.TextInput,
                    label=_('Reference 3 prefix'),
                    help_text=_('Have to match the reference 3 prefix configured as plugin\'s callback.'),
                    required=True,
                    regex='[A-Z0-9]{3}',
                )),
            ]
        )

    def settings_form_clean(self, cleaned_data):
        # Remove trailing slash from api_url
        api_url = re.sub(r'/$', '', cleaned_data.get('payment_promptpay_scb_api_url'))
        cleaned_data['payment_promptpay_scb_api_url'] = api_url

        return cleaned_data

    def get_callback_secret(self):
        secret = self.settings.callback_secret
        if secret is None:
            secret = get_random_string(length=32, allowed_chars=string.ascii_letters + string.digits)
            self.settings.callback_secret = secret
            # FIXME: better way to persist this settings?
            self.event.save()

        return secret

    def settings_content_render(self, request):
        callback_content = "<div class='alert alert-info'>%s <b>%s</b><br />" \
                            "<code>%s</code></div>" % (
            _("Config this URL as the payment confirmation endpoint at SCB's portal."),
            _("Anyone knowing this endpoint can confirm their payment, so keep it secret."),
            build_absolute_uri(self.event, 'plugins:pretix_promptpay_scb:callback',
                                kwargs={ 'callback_secret': self.get_callback_secret() })
        )

        return callback_content

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

    def get_event_ref1(self):
        """
            Merge choosen prefix and event slug. Make sure it doesn't exceed 20 chars.
            Also called from the payment callback view.
        """

        # Remove all non-alphanum from slug and uppercase it.
        slugRef = re.sub(r'[^A-Z0-9]*', '', self.event.slug.upper())
        # Shorten to the first 20 chars.
        return slugRef[:20]

    def execute_payment(self, request, payment):
        api = ScbPartnerApi(
            base_url=self.settings.api_url,
            app_key=self.settings.application_key,
            app_secret=self.settings.application_secret,
            cache=self.event.cache,
        )

        # All references are [A-Z0-9]{1,20}, thus some transformation is
        # needed before putting things into slug.
        
        ref1 = self.get_event_ref1()

        # Would love to use payment.full_id, but that contains '-'.
        ref2 = '%sP%d' % (payment.order.code, payment.local_id)

        # Have nothing to append to ref3 yet.
        ref3 = self.settings.ref3_prefix

        try:
            qr_response = api.qrcode_create_biller(
                amount=payment.amount,
                ppId=self.settings.pp_id,
                ref1=ref1,
                ref2=ref2,
                ref3=ref3,
            )
        except ScbPartnerApi.BussinessError as e:
            logger.exception('Error on creating QR code: ' + str(e))
            raise PaymentException(_('เกิดข้อผิดพลาดในการสร้าง QR code')) from e

        # Keep only the QR image, for displaying in our custom view.
        qr_image = qr_response['qrImage']
        payment.info_data = { 'qr_image': qr_image }
        payment.state = OrderPayment.PAYMENT_STATE_PENDING
        payment.save()

        return eventreverse(
            obj=self.event,
            name='plugins:pretix_promptpay_scb:show_qr',
            kwargs={
                'order': payment.order.code,
                'payment': payment.pk,
                'secret': payment.order.secret
            }
        )

    @property
    def test_mode_message(self):
        if self.settings.api_url.endswith('/sandbox'):
            return _('The SCB sandbox is being used. You need to use SCB Simulator app to test. '
                     'Download the app at <a href="{link}">{link}</a>') \
                    .format(link='https://developer.scb/#/documents/documentation/basics/developer-sandbox.html')