import datetime
import json
from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.utils.timezone import now
from django_scopes import scope

from pretix.base.models import (
    Event, Order, OrderPayment, OrderRefund, Organizer, Team, User,
)
from pretix.multidomain.urlreverse import eventreverse

@pytest.fixture
def env(client):
    orga = Organizer.objects.create(name='SCB', slug='SCB')
    with scope(organizer=orga):
        event = Event.objects.create(
            organizer=orga, name='SCB PromptPay QR', slug='promptpay',
            date_from=datetime.datetime(now().year + 1, 12, 26, tzinfo=datetime.timezone.utc),
            plugins='pretix_promptpay_scb',
            live=True
        )
        order = Order.objects.create(
            code='FOOBAR', event=event, email='dummy@dummy.test',
            status=Order.STATUS_PENDING,
            datetime=now(), expires=now() + datetime.timedelta(days=10),
            total=Decimal('13.37'),
        )
        payment = order.payments.create(
            amount=order.total,
            provider='promptpay_scb',
            state=OrderPayment.PAYMENT_STATE_PENDING,
            info=json.dumps({
                # 1x1 GIF.
                'qr_image': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=',
            }),
            # What else?
        )

    return client, orga, event, order, payment

def get_show_qr_url(event, payment):
    return eventreverse(
        obj=event,
        name='plugins:pretix_promptpay_scb:show_qr',
        kwargs={
            'order': payment.order.code,
            'payment': payment.pk,
            'secret': payment.order.secret
        }
    )

@pytest.mark.django_db
def test_pending_payment(env):
    client, orga, event, order, payment = env

    url = get_show_qr_url(event, payment)
    response = client.get(url)
    assert response.status_code == 200 # No redirect
    assert response.context['qr_data_url'].endswith(payment.info_data['qr_image'])

@pytest.mark.django_db
def test_paid_payment(env):
    client, orga, event, order, payment = env
    with scope(organizer=orga):
        payment.confirm()

    url = get_show_qr_url(event, payment)
    response = client.get(url)

    assert response['Location'].endswith('?paid=yes')

@pytest.mark.django_db
def test_paid_payment_not_covered(env):
    client, orga, event, order, payment = env
    with scope(organizer=orga):
        order.total += Decimal('10')
        order.save()

        payment.confirm()

    url = get_show_qr_url(event, payment)
    response = client.get(url)

    assert response['Location'].endswith('?thanks=yes')

@pytest.mark.django_db
def test_failed_payment(env):
    client, orga, event, order, payment = env
    with scope(organizer=orga):
        payment.fail()

    url = get_show_qr_url(event, payment)
    response = client.get(url)

    assert response['Location'] == '/%s/%s/order/%s/%s/' % (
        orga.slug, event.slug, order.code, order.secret
    )
