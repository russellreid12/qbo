from rest_framework import serializers


class MoveSerializer(serializers.Serializer):
    fromSquare = serializers.IntegerField(required=True)
    toSquare = serializers.IntegerField(required=True)
    eat = serializers.BooleanField(required=True)
    crowned = serializers.BooleanField(required=True)
