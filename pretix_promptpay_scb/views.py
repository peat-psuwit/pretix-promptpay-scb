from django.contrib import messages
from django.http.response import HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.views.generic import TemplateView

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
        ctx['qr_data_url'] = self.qr_data_url
        return ctx