from collections import OrderedDict

from django import forms
from django.utils.translation import gettext_lazy as _

from pretix.base.payment import BasePaymentProvider

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

    def checkout_confirm_render(self):
        return '''
ระบบจะแสดง QR Code ในหน้าถัดไป โปรดชำระเงินภายใน 10 นาที มิฉะนั้น ท่านจะต้องเริ่มการชำระเงินอีกครั้ง
'''