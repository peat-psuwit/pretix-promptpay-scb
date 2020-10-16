from django.conf.urls import url
from pretix.multidomain import event_url

from . import views

event_patterns = [
    url(r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/pay/(?P<payment>[0-9]+)/promptpay_scb_show_qr$',
        views.ShowQrView.as_view(), name='show_qr'),
    url(r'^order/(?P<order>[^/]+)/(?P<secret>[A-Za-z0-9]+)/pay/(?P<payment>[0-9]+)/promptpay_scb_state$',
        views.PaymentStateView.as_view(), name='payment_state'),
    event_url(r'^_promptpay_scb/callback/(?P<callback_secret>[A-Za-z0-9]+)$',
        views.callback_view, name='callback', require_live=False),
]