import datetime

from rqalpha.utils.testing import MagicMock, BookingFixture, RQAlphaTestCase
from rqalpha.const import POSITION_DIRECTION, SIDE, POSITION_EFFECT
from rqalpha.events import Event, EVENT
from rqalpha.model.trade import Trade


class BookingTestCase(BookingFixture, RQAlphaTestCase):
    def __init__(self, *args, **kwargs):
        super(BookingTestCase, self).__init__(*args, **kwargs)

    def assertPositions(self, positions_data):
        self.assertEqual(
            {(p.direction, p.order_book_id, p.today_quantity, p.old_quantity) for p in self.booking.get_positions()},
            positions_data
        )
        for direction, order_book_id, today_quanttiy, old_quantity in positions_data:
            self.assertObj(
                self.booking.get_position(order_book_id, direction),
                today_quantity=today_quanttiy, old_quantity=old_quantity, quantity=(today_quanttiy + old_quantity)
            )

    def test_booking(self):
        from rqalpha.model.booking import BookingPosition

        def mock_get_instrument(order_book_id):
            not_delisted_ins = MagicMock()
            not_delisted_ins.de_listed_date = datetime.datetime.max
            not_delisted_ins.type = "Future"

            delisted_ins = MagicMock()
            delisted_ins.de_listed_date = datetime.datetime.min
            delisted_ins.type = "Future"
            if order_book_id == "TF1812":
                return delisted_ins
            return not_delisted_ins

        self.long_positions["RB1812"] = BookingPosition(
            self.data_proxy, "RB1812", POSITION_DIRECTION.LONG, old_quantity=1, today_quantity=3
        )
        self.short_positions["TF1812"] = BookingPosition(
            self.data_proxy, "TF1812", POSITION_DIRECTION.SHORT, today_quantity=4
        )

        self.assertPositions({
            (POSITION_DIRECTION.LONG, "RB1812", 3, 1),
            (POSITION_DIRECTION.SHORT, "TF1812", 4, 0)
        })

        self.env.event_bus.publish_event(Event(EVENT.TRADE, trade=Trade.__from_create__(
            0, 0, 2, SIDE.SELL, POSITION_EFFECT.OPEN, "RB1812"
        )))
        self.assertPositions({
            (POSITION_DIRECTION.LONG, "RB1812", 3, 1),
            (POSITION_DIRECTION.SHORT, "RB1812", 2, 0),
            (POSITION_DIRECTION.SHORT, "TF1812", 4, 0)
        })
        self.env.event_bus.publish_event(Event(EVENT.TRADE, trade=Trade.__from_create__(
            0, 0, 3, SIDE.SELL, POSITION_EFFECT.CLOSE, "RB1812"
        )))
        self.assertPositions({
            (POSITION_DIRECTION.LONG, "RB1812", 1, 0),
            (POSITION_DIRECTION.SHORT, "RB1812", 2, 0),
            (POSITION_DIRECTION.SHORT, "TF1812", 4, 0)
        })

        with self.mock_data_proxy_method("instruments", mock_get_instrument):
            self.env.trading_dt = datetime.datetime(2018, 8, 31)
            self.env.event_bus.publish_event(Event(EVENT.POST_SETTLEMENT))
            self.assertPositions({
                (POSITION_DIRECTION.LONG, "RB1812", 0, 1),
                (POSITION_DIRECTION.SHORT, "RB1812", 0, 2),
            })
