from django.db import models


class County(models.Model):
    fips = models.CharField(max_length=5, unique=True, db_index=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.fips})"


class ElectionResult(models.Model):
    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name="results")
    year = models.IntegerField(db_index=True)
    votes_dem = models.IntegerField()
    votes_gop = models.IntegerField()
    total_votes = models.IntegerField()
    per_dem = models.FloatField()
    per_gop = models.FloatField()
    per_point_diff = models.FloatField()

    class Meta:
        unique_together = ("county", "year")
        ordering = ["year"]

    def __str__(self):
        return f"{self.county.name} {self.year}"

    @property
    def winner(self):
        return "Democratic" if self.per_dem > self.per_gop else "Republican"

    @property
    def margin_pct(self):
        return round(abs(self.per_point_diff) * 100, 1)
