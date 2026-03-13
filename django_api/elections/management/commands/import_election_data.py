"""
Management command: import election CSV data into the SQLite database.

Usage (from django_api/ directory):
    python manage.py import_election_data

The command clears and re-imports all data so it is safe to run multiple times.
"""
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand

from elections.models import County, ElectionResult

# Each year's CSV has slightly different column names — map them here.
YEAR_CONFIG = [
    {
        "year": 2016,
        "file": "2016.csv",
        "state_col": "state_abbr",
        "state_val": "TX",
        "fips_col": "combined_fips",
    },
    {
        "year": 2020,
        "file": "2020.csv",
        "state_col": "state_name",
        "state_val": "Texas",
        "fips_col": "county_fips",
    },
    {
        "year": 2024,
        "file": "2024.csv",
        "state_col": "state_name",
        "state_val": "Texas",
        "fips_col": "county_fips",
    },
]

# Data directory sits one level above django_api/
DATA_DIR = settings.BASE_DIR.parent / "data"


class Command(BaseCommand):
    help = "Import election CSV files into the database (clears existing data first)"

    def handle(self, *args, **options):
        self.stdout.write("Clearing existing data...")
        ElectionResult.objects.all().delete()
        County.objects.all().delete()

        total_results = 0

        for cfg in YEAR_CONFIG:
            path = DATA_DIR / cfg["file"]
            if not path.exists():
                self.stderr.write(self.style.WARNING(f"  Skipping {cfg['file']} — file not found at {path}"))
                continue

            df = pd.read_csv(path)
            df = df[df[cfg["state_col"]] == cfg["state_val"]].copy()
            df["fips"] = df[cfg["fips_col"]].apply(lambda x: f"{int(x):05d}")

            for col in ["votes_dem", "votes_gop", "total_votes", "per_dem", "per_gop", "per_point_diff"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df = df.dropna(subset=["per_dem", "per_gop", "total_votes"])

            imported = 0
            for _, row in df.iterrows():
                county, _ = County.objects.get_or_create(
                    fips=row["fips"],
                    defaults={"name": row["county_name"]},
                )
                ElectionResult.objects.update_or_create(
                    county=county,
                    year=cfg["year"],
                    defaults={
                        "votes_dem": int(row["votes_dem"]),
                        "votes_gop": int(row["votes_gop"]),
                        "total_votes": int(row["total_votes"]),
                        "per_dem": float(row["per_dem"]),
                        "per_gop": float(row["per_gop"]),
                        "per_point_diff": float(row["per_point_diff"]),
                    },
                )
                imported += 1

            total_results += imported
            self.stdout.write(f"  {cfg['year']}: {imported} counties imported.")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {County.objects.count()} counties, {total_results} election results."
            )
        )
