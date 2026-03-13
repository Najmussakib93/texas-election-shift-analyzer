from rest_framework import serializers
from .models import County, ElectionResult


class ElectionResultSerializer(serializers.ModelSerializer):
    winner = serializers.CharField(read_only=True)
    margin_pct = serializers.FloatField(read_only=True)

    class Meta:
        model = ElectionResult
        fields = [
            "year",
            "votes_dem",
            "votes_gop",
            "total_votes",
            "per_dem",
            "per_gop",
            "per_point_diff",
            "winner",
            "margin_pct",
        ]


class CountyDetailSerializer(serializers.ModelSerializer):
    results = ElectionResultSerializer(many=True, read_only=True)

    class Meta:
        model = County
        fields = ["fips", "name", "results"]


class CountySummarySerializer(serializers.ModelSerializer):
    winner_2024 = serializers.SerializerMethodField()
    margin_2024 = serializers.SerializerMethodField()

    class Meta:
        model = County
        fields = ["fips", "name", "winner_2024", "margin_2024"]

    def get_winner_2024(self, obj):
        result = obj.results.filter(year=2024).first()
        return result.winner if result else None

    def get_margin_2024(self, obj):
        result = obj.results.filter(year=2024).first()
        return result.margin_pct if result else None
