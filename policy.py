"""Pure decision layer; no network access or account mutations."""
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))


def plan(lectures, now, mode, managed_ids=()):
    """ISO timestamps must include timezone. Only manage tracked reservations.

    Input fields: id, title, starts_at, opens_at, closes_at, status, reservable.
    status: unreserved, waiting, won, lost, other, unknown.
    cancellable must be verified from the current page, not inferred.
    unknown means an unreadable/unrecognized page, not a valid non-winning status.
    """
    if now.tzinfo is None:
        raise ValueError('now must include timezone')
    if mode not in ('reserve', 'results'):
        raise ValueError('mode must be reserve or results')
    now = now.astimezone(CST)
    yesterday = now.date() - timedelta(days=1)
    managed = set(managed_ids)
    actions = []
    seen = set()
    parsed = []
    for item in lectures:
        if item['id'] in seen:
            raise ValueError('duplicate lecture id')
        seen.add(item['id'])
        dates = []
        for key in ('starts_at', 'opens_at', 'closes_at'):
            value = datetime.fromisoformat(item[key])
            if value.tzinfo is None:
                raise ValueError(key + ' must include timezone')
            dates.append(value.astimezone(CST))
        parsed.append((dates[0], item, dates[1], dates[2]))
    for starts, item, opens, closes in sorted(parsed, key=lambda row: (row[0], row[1]['id'])):
        if starts <= now:
            continue
        action = None
        if mode == 'reserve':
            first_draw = datetime.combine(opens.date() + timedelta(days=1), datetime.min.time(), CST) + timedelta(hours=6)
            if (opens.date() == yesterday and opens <= now < min(closes, first_draw)
                    and item['status'] == 'unreserved' and item.get('reservable') is True
                    and item['id'] not in managed):
                action = 'reserve'
        elif item['id'] in managed:
            if item['status'] == 'won':
                action = 'notify_winner'
            elif item['status'] in ('lost', 'waiting', 'other') and item.get('cancellable') is True:
                first_check = datetime.combine(opens.date() + timedelta(days=1), datetime.min.time(), CST) + timedelta(hours=6, minutes=10)
                if now >= first_check and now < closes:
                    action = 'cancel'
            elif item['status'] != 'unreserved':
                action = 'recheck'
        if action:
            actions.append({'id': item['id'], 'title': item['title'], 'action': action})
    return actions
