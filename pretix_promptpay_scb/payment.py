from pretix.base.payment import BasePaymentProvider

class PromptPayScbPaymentProvider(BasePaymentProvider):
    identifier = 'promptpay_scb'
    verbose_name = 'Thai PromptPay QR via SCB API'
    public_name = 'PromptPay QR (โมบายแบงก์กิ้ง)'

    def checkout_confirm_render(self):
        return '''
ระบบจะแสดง QR Code ในหน้าถัดไป โปรดชำระเงินภายใน 10 นาที มิฉะนั้น ท่านจะต้องเริ่มการชำระเงินอีกครั้ง
'''