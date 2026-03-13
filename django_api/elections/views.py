from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import County, ElectionResult
from .serializers import CountyDetailSerializer, CountySummarySerializer


class CountyListView(APIView):
    """
    GET /api/counties/
    Returns all 254 Texas counties with their 2024 result summary.
    """

    def get(self, request):
        counties = County.objects.prefetch_related("results").all()
        serializer = CountySummarySerializer(counties, many=True)
        return Response(serializer.data)


class CountyDetailView(APIView):
    """
    GET /api/counties/<fips>/
    Returns the full election history (2016, 2020, 2024) for one county.
    """

    def get(self, request, fips):
        fips = str(fips).zfill(5)
        try:
            county = County.objects.prefetch_related("results").get(fips=fips)
        except County.DoesNotExist:
            return Response(
                {"error": f"No county found with FIPS {fips}."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = CountyDetailSerializer(county)
        return Response(serializer.data)


class ShiftsView(APIView):
    """
    GET /api/shifts/?from_year=2016&to_year=2024
    Returns the 15 counties with the largest partisan swings between two elections,
    ranked by absolute shift in Democratic vote share.
    """

    VALID_YEARS = {2016, 2020, 2024}

    def get(self, request):
        try:
            from_year = int(request.query_params.get("from_year", 2016))
            to_year = int(request.query_params.get("to_year", 2024))
        except (TypeError, ValueError):
            return Response(
                {"error": "from_year and to_year must be integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if from_year not in self.VALID_YEARS or to_year not in self.VALID_YEARS:
            return Response(
                {"error": f"Years must be one of {sorted(self.VALID_YEARS)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if from_year >= to_year:
            return Response(
                {"error": "from_year must be less than to_year."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from_results = {
            r.county_id: r
            for r in ElectionResult.objects.filter(year=from_year).select_related("county")
        }
        to_results = {
            r.county_id: r
            for r in ElectionResult.objects.filter(year=to_year).select_related("county")
        }

        shifts = []
        for county_id, from_r in from_results.items():
            if county_id not in to_results:
                continue
            to_r = to_results[county_id]
            shift = (to_r.per_dem - from_r.per_dem) * 100
            shifts.append(
                {
                    "county_fips": from_r.county.fips,
                    "county_name": from_r.county.name,
                    f"dem_pct_{from_year}": round(from_r.per_dem * 100, 1),
                    f"dem_pct_{to_year}": round(to_r.per_dem * 100, 1),
                    "shift_pts": round(shift, 1),
                    "direction": "Toward Dem" if shift > 0 else "Toward GOP",
                }
            )

        shifts.sort(key=lambda x: abs(x["shift_pts"]), reverse=True)
        return Response(shifts[:15])
