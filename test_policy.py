import unittest
from datetime import datetime
from policy import plan


def lecture(id='a', **changes):
    result = dict(id=id, title=id, starts_at='2026-09-18T16:40:00+08:00',
                  opens_at='2026-09-14T21:30:00+08:00', closes_at='2026-09-18T16:10:00+08:00',
                  status='unreserved', reservable=True, cancellable=True)
    result.update(changes)
    return result


class PolicyTests(unittest.TestCase):
    def test_midnight_previous_day_and_order(self):
        rows = [lecture('later', starts_at='2026-09-23T16:40:00+08:00'), lecture('near'),
                lecture('old', opens_at='2026-09-11T21:30:00+08:00')]
        actions = plan(rows, datetime.fromisoformat('2026-09-14T16:00:00+00:00'), 'reserve')
        self.assertEqual([a['id'] for a in actions], ['near', 'later'])

    def test_late_scheduler_must_not_enter_after_first_draw(self):
        self.assertEqual(plan([lecture()], datetime.fromisoformat('2026-09-15T06:01:00+08:00'), 'reserve'), [])

    def test_waiting_cancels_after_first_check(self):
        actions = plan([lecture(status='waiting')], datetime.fromisoformat('2026-09-15T06:20:00+08:00'), 'results', ['a'])
        self.assertEqual(actions[0]['action'], 'cancel')

    def test_waiting_before_first_check_never_cancels(self):
        actions = plan([lecture(status='waiting')], datetime.fromisoformat('2026-09-15T06:09:00+08:00'), 'results', ['a'])
        self.assertFalse(any(a['action'] == 'cancel' for a in actions))

    def test_unreadable_state_never_cancels(self):
        actions = plan([lecture(status='unknown')], datetime.fromisoformat('2026-09-15T06:20:00+08:00'), 'results', ['a'])
        self.assertEqual(actions[0]['action'], 'recheck')

    def test_missing_cancel_button_never_cancels(self):
        actions = plan([lecture(status='waiting', cancellable=False)], datetime.fromisoformat('2026-09-15T06:20:00+08:00'), 'results', ['a'])
        self.assertEqual(actions[0]['action'], 'recheck')

    def test_unmanaged_reservations_untouched(self):
        self.assertEqual(plan([lecture(status='lost')], datetime.fromisoformat('2026-09-15T06:20:00+08:00'), 'results'), [])

    def test_confirmed_loss_and_winner(self):
        actions = plan([lecture('a', status='lost'), lecture('b', status='won')],
                       datetime.fromisoformat('2026-09-15T06:20:00+08:00'), 'results', ['a', 'b'])
        self.assertEqual([a['action'] for a in actions], ['cancel', 'notify_winner'])

    def test_no_rebooking_tracked_cancellation(self):
        self.assertEqual(plan([lecture()], datetime.fromisoformat('2026-09-15T00:00:00+08:00'), 'reserve', ['a']), [])


if __name__ == '__main__':
    unittest.main()
