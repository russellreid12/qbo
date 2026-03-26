import importlib.util
import os

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from panel.serializers.move_serializers import MoveSerializer

class MoveView(APIView):
    def post(self, request):
        """
        Qbo talk moves
        :param request:
        :return:
        """
        serializer = MoveSerializer(data=request.data, many=True)

        if serializer.is_valid():
            moves = serializer.validated_data

            text_to_speech = move_text(moves)

            # Call system module for convert text to speech
            # Load external script 'Speak.py' from filesystem
            try:
                _speak_path = '{}/../../../Speak.py'.format(os.path.dirname(os.path.abspath(__file__)))
                _spec = importlib.util.spec_from_file_location('speak', _speak_path)
                speak = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(speak)

                speak.SpeechText_2(text_to_speech, text_to_speech)
            except (IOError, ImportError) as e:
                return Response(str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response(text_to_speech, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def move_text(moves):
    """
    Create a description string from moves
    :param moves: moves array with the next shape:
        [
            {
                "fromSquare": 12,
                "toSquare": 16,
                "eat": false,
                "crowned": true
            },
        ]
    :return: string text to speech
    """

    # $1 total moves
    # $2 initial square
    # $3 final square
    base_text = 'I move{} from square {} to {}'

    len_moves = len(moves)

    # Only append 'times' if has more than 1
    total_moves = ' {} times'.format(len_moves) if len_moves > 1 else ''
    initial_square = transform_piece_key(moves[0]['fromSquare'])
    final_square = transform_piece_key(moves[len_moves - 1]['toSquare'])

    texts = [
        base_text.format(total_moves, initial_square, final_square),
    ]

    # append eat
    if moves[0]['eat']:
        # Add number of times if more than 1
        times = '{} pieces'.format(len_moves) if len_moves > 1 else 'a piece'
        texts.append('I capture {}'.format(times))

    # crowned if last move is 'crowned'
    if moves[len(moves) - 1]['crowned']:
        texts.append('I\'m crowned')

    return {
        1: lambda: texts[0],
        2: lambda: '{} and {}'.format(texts[0], texts[1]),
        3: lambda: '{}, {} and {}'.format(texts[0], texts[1], texts[2])
    }.get(len(texts))() + '.'


def transform_piece_key(key):
    """
    Get piece's key and transform to visual key for final player
    :param key:
    :return: integer
    """
    return {
        28: 32,     29: 31,     30: 30,     31: 29,
        24: 28,     25: 27,     26: 26,     27: 25,
        20: 24,     21: 23,     22: 22,     23: 21,
        16: 20,     17: 19,     18: 18,     19: 17,
        12: 16,     13: 15,     14: 14,     15: 13,
        8:  12,     9:  11,     10: 10,     11: 9,
        4:  8,      5:  7,      6:  6,       7: 5,
        0:  4,      1:  3,      2:  2,       3: 1,
    }.get(key)
