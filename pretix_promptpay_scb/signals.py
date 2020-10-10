from django.dispatch import receiver

from pretix.base.signals import register_payment_providers

@receiver(register_payment_providers, dispatch_uid="payment_promptpay_scb")
def register_payment_provider(sender, **kwargs):
    from .payment import PromptPayScbPaymentProvider
    return PromptPayScbPaymentProvider
