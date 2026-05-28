"""Phase 2 ORM test for P3-LEAD-MAIL-ALIAS — multichannel.enquiry.message_new."""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEnquiryMessageNewORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Enquiry = cls.env['multichannel.enquiry']

    def test_message_new_creates_enquiry_with_email_alias_source(self):
        msg_dict = {
            'subject': 'Question about my order',
            'email_from': 'buyer@example.com',
            'body': 'Can you ship sooner?',
        }
        enquiry = self.Enquiry.message_new(msg_dict)
        self.assertTrue(enquiry)
        self.assertEqual(enquiry.source, 'email_alias')
        self.assertEqual(enquiry.subject, 'Question about my order')
        self.assertEqual(enquiry.partner_email, 'buyer@example.com')

    def test_message_new_resolves_existing_partner(self):
        partner = self.env['res.partner'].create({
            'name': 'Resolved Buyer',
            'email': 'resolved@example.com',
        })
        msg_dict = {
            'subject': 'Hello',
            'email_from': 'resolved@example.com',
        }
        enquiry = self.Enquiry.message_new(msg_dict)
        self.assertEqual(enquiry.partner_id, partner)

    def test_message_new_with_custom_values_overrides_defaults(self):
        msg_dict = {'subject': 'orig', 'email_from': 'x@y.com'}
        enquiry = self.Enquiry.message_new(
            msg_dict, custom_values={'subject': 'custom'},
        )
        self.assertEqual(enquiry.subject, 'custom')
