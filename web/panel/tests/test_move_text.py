from django.test import SimpleTestCase
from panel.views.moves_views import move_text


class MovesTest(SimpleTestCase):
    def test_move_test(self):
        self.assertEquals(
            'I move from square 24 to 19.',
            move_text([
                {
                    "fromSquare": 20,
                    "toSquare": 17,
                    "eat": False,
                    "crowned": False
                },
            ])
        )

        self.assertEquals(
            'I move 2 times from square 24 to 6 and I capture 2 pieces.',
            move_text([
                {
                    "fromSquare": 20,
                    "toSquare": 13,
                    "eat": True,
                    "crowned": False
                },
                {
                    "fromSquare": 13,
                    "toSquare": 6,
                    "eat": True,
                    "crowned": False
                },
            ])
        )

        self.assertEquals(
            'I move from square 8 to 3 and I\'m crowned.',
            move_text([
                {
                    "fromSquare": 4,
                    "toSquare": 1,
                    "eat": False,
                    "crowned": True
                },
            ])
        )

        self.assertEquals(
            'I move 3 times from square 26 to 3, I capture 3 pieces and I\'m crowned.',
            move_text([
                {
                    "fromSquare": 26,
                    "toSquare": 17,
                    "eat": True,
                    "crowned": False
                },
                {
                    "fromSquare": 17,
                    "toSquare": 8,
                    "eat": True,
                    "crowned": False
                },
                {
                    "fromSquare": 8,
                    "toSquare": 1,
                    "eat": True,
                    "crowned": True
                },
            ])
        )
