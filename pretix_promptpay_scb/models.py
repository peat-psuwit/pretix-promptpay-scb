from django.db import models

from pretix.base.models import Order, OrderPayment

class SCBTransaction(models.Model):
    '''
        This model exists solely to provide idempotency for an SCB transaction.
        This maps one-to-one to an OrderPayment; any other info are saved in
        that model.
    '''

    STATE_CREATED = 'created'
    STATE_MATCHED = 'match'
    STATE_NOMATCH = 'nomatch'
    STATE_CHOICES = [
        (STATE_CREATED, 'Created'),
        (STATE_MATCHED, 'Matching order is found'),
        (STATE_NOMATCH, 'Matching order not found'),
    ]

    transaction_id = models.CharField(max_length=64, primary_key=True)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=STATE_CREATED)
    payment = models.OneToOneField(
        OrderPayment,
        on_delete=models.PROTECT,
        related_name='scb_transaction',
        null=True)
