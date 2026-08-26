from groups.models import Group
from rest_framework import serializers

from clubs.models import Club
from scheduling.models import Activity, Season


class ClubSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = ["slug", "name", "city"]


class SeasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Season
        fields = ["id", "name", "start_date", "end_date"]


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name"]


class ActivitySerializer(serializers.ModelSerializer):
    group = GroupSerializer(read_only=True)

    class Meta:
        model = Activity
        fields = [
            "id",
            "title",
            "activity_type",
            "date",
            "start_time",
            "end_time",
            "location",
            "is_cancelled",
            "group",
        ]
