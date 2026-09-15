import unittest
from unittest.mock import Mock

from bot import no_ticket


class NoTicketTests(unittest.TestCase):
    def page(self, text):
        page = Mock()
        page.locator.return_value.inner_text.return_value = text
        return page

    def test_visible_rejection(self):
        self.assertTrue(no_ticket(self.page('票不足，预约失败')))

    def test_dialog_rejection(self):
        self.assertTrue(no_ticket(self.page('Lecture list'), ['没有可用票']))

    def test_normal_page(self):
        self.assertFalse(no_ticket(self.page('Open for reservation')))

    def test_unrelated_ticket_text(self):
        self.assertFalse(no_ticket(self.page('No ticket refunds after the deadline')))
