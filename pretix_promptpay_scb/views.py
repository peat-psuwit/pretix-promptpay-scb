import json
import re

from django.contrib import messages
from django.http.response import JsonResponse, Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, View

from pretix.base.models.items import Quota
from pretix.base.models.orders import Order, OrderPayment
from pretix.presale.views import EventViewMixin
from pretix.presale.views.order import OrderDetailMixin

class ShowQrView(EventViewMixin, OrderDetailMixin, TemplateView):
    template_name = 'pretix_promptpay_scb/order_pay_show_qr.html'

    @cached_property
    def payment(self):
        return get_object_or_404(self.order.payments, pk=self.kwargs['payment'])

    def dispatch(self, request, *args, **kwargs):
        self.request = request
        if not self.order:
            raise Http404(_('Unknown order code or not authorized to access this order.'))

        if self.payment.provider != 'promptpay_scb':
            raise Http404(_('Wrong payment provider'))

        if self.payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED:
            if self.order.status == Order.STATUS_PAID:
                return redirect(self.get_order_url() + '?paid=yes')
            else:
                return redirect(self.get_order_url() + '?thanks=yes')

        qr_image = self.payment.info_data['qr_image']
        if qr_image is None:
            messages.error(request, _('เกิดข้อผิดพลาดในการสร้าง QR code'))
            payment.fail()
            return redirect(self.get_order_url())

        # SCB image is a GIF file.
        self.qr_data_url = 'data:image/gif;base64,' + qr_image

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['order'] = self.order
        ctx['payment'] = self.payment
        ctx['qr_data_url'] = self.qr_data_url
        return ctx

class PaymentStateView(OrderDetailMixin, View):
    @cached_property
    def payment(self):
        return get_object_or_404(self.order.payments, pk=self.kwargs['payment'])

    def dispatch(self, request, *args, **kwargs):
        self.request = request
        if not self.order:
            raise Http404(_('Unknown order code or not authorized to access this order.'))

        if self.payment.provider != 'promptpay_scb':
            raise Http404(_('Wrong payment provider'))

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        state = self.payment.state
        redirect_to = None

        if self.payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED:
            if self.order.status == Order.STATUS_PAID:
                redirect_to = self.get_order_url() + '?paid=yes'
            else:
                redirect_to = self.get_order_url() + '?thanks=yes'

        return JsonResponse({
            'state': state,
            'redirectTo': redirect_to,
        })

@csrf_exempt
@require_POST
def callback_view(request, *args, **kwargs):
    event = request.event
    payment_provider = event.get_payment_providers()['promptpay_scb']
    if not payment_provider.is_enabled:
        raise Http404()

    # First, make sure the callback_secret matches.
    callback_secret = kwargs['callback_secret']
    if callback_secret != payment_provider.settings.callback_secret:
        raise Http404() # Intentionally be opaque, because it's a part of the URL.

    try:
        confirmation = json.load(request) # Note, HttpRequest implements read().
    except json.JSONDecodeError:
        return HttpResponseBadRequest()

    try:
        ref1 = confirmation['billPaymentRef1']
        ref2 = confirmation['billPaymentRef2']
    except KeyError:
        return HttpResponseBadRequest()

    # Verify the paid event from ref1
    if ref1 != payment_provider.get_event_ref1():
        # FIXME: is this a good response?
        return HttpResponseBadRequest()

    # Parse which payment it is from ref2
    parsed_ref2 = re.match(r'^(?P<order>[^/]+)P(?P<pay_local_id>[0-9]+)$', ref2)
    if parsed_ref2 is None:
        return HttpResponseBadRequest()

    order_code = parsed_ref2.group('order')
    pay_local_id = int(parsed_ref2.group('pay_local_id'))

    payment = get_object_or_404(OrderPayment,
                order__code=order_code, local_id=pay_local_id)

    try:
        payment.confirm()
    except Quota.QuotaExceededException:
        # Do not return error. The payment is marked paid nonetheless.
        # We still have to tell SCB that yes, we acknowledged that.
        pass

    # Replace the payment info with confirmation, used to display info
    # in admin view (not implemented yet).
    payment.info_data = { 'confirmation': confirmation }
    payment.save()

    # Respond in a specific format defined by SCB
    return JsonResponse({
        'resCode': '00', # Yes, a string
        'resDesc': 'success',
        'transactionId': confirmation['transactionId'],
    })