from django.utils.translation import gettext_lazy

try:
    from pretix.base.plugins import PluginConfig
except ImportError:
    raise RuntimeError("Please use pretix 2.7 or above to run this plugin!")

__version__ = '1.0.0'


class PluginApp(PluginConfig):
    name = 'pretix_promptpay_scb'
    verbose_name = 'SCB PromptPay QR'

    class PretixPluginMeta:
        name = gettext_lazy('SCB PromptPay QR')
        author = 'Ratchanan Srirattanamet'
        description = gettext_lazy('Pretix payment plugin for Thai PromptPay QR code, using SCB API')
        visible = True
        version = __version__
        category = 'PAYMENT'
        compatibility = "pretix>=2.7.0"

    def ready(self):
        from . import signals  # NOQA


default_app_config = 'pretix_promptpay_scb.PluginApp'
