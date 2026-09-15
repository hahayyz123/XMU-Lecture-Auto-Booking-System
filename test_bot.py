import unittest
from bot import decode_row, parse_date


class TableTests(unittest.TestCase):
    def row(self, status):
        return ['Series Seminar', 'Example', 'Speaker', 'Chinese', 'Room',
                '2026-09-18 (Friday) 16:40-18:00', '2026-09-14 21:30:00',
                '2026-09-18 16:10:00', '70', '100', '', 'Open for reservation',
                status, 'Cancel my reservation']

    def test_dates(self):
        self.assertEqual(parse_date(self.row('')[5]), '2026-09-18T16:40:00+08:00')

    def test_won_and_waiting_are_distinct(self):
        self.assertEqual(decode_row(self.row('已抽中 (Successfully reserved)'))['status'], 'won')
        self.assertEqual(decode_row(self.row('等待抽签 (Waiting for the draw)'))['status'], 'waiting')

    def test_empty_status_not_treated_as_loss(self):
        self.assertEqual(decode_row(self.row(''))['status'], 'unknown')

    def test_layout_change_fails(self):
        with self.assertRaises(ValueError):
            decode_row(self.row('')[:-1])

    def test_identity_does_not_depend_on_reservation_count(self):
        row = self.row('等待抽签')
        before = decode_row(row)['id']
        row[9] = '101'
        self.assertEqual(before, decode_row(row)['id'])


if __name__ == '__main__':
    unittest.main()
