"""Tests for DataForSEO rankings and SEO report generation."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_dataforseo_ranking_stored():
    """DataForSEO API response is parsed and ranking position is returned."""
    from services.dataforseo import get_local_rankings

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "tasks": [{
            "result": [{
                "items": [
                    {"type": "organic", "rank_absolute": 3, "url": "https://sydneydentalcare.com.au"},
                    {"type": "paid", "rank_absolute": 1, "url": "https://ad.example.com"},
                ]
            }]
        }]
    }

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post.return_value = mock_response

    with patch("services.dataforseo.httpx.AsyncClient", return_value=mock_client):
        result = await get_local_rankings(
            keyword="dentist bondi",
            location="Bondi Junction",
            client_suburb="Bondi",
        )

    assert result["keyword"] == "dentist bondi"
    assert result["position"] == 3
    assert result["url"] == "https://sydneydentalcare.com.au"


@pytest.mark.asyncio
async def test_seo_report_generates():
    """SEO report generation calls Claude and returns report text."""
    from services.claude import generate_seo_report

    report_text = (
        "Your rankings improved this week! 'dentist Bondi' moved from "
        "position 8 to 3. We recommend updating your Google listing with "
        "fresh photos. Trajectory: improving."
    )
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=report_text)]
    mock_client_instance = MagicMock()
    mock_client_instance.messages.create.return_value = mock_response

    this_week = [
        {"keyword": "dentist bondi", "position": 3, "url": "https://sydneydentalcare.com.au"},
        {"keyword": "dental clinic bondi", "position": 7, "url": "https://sydneydentalcare.com.au"},
    ]
    last_week = [
        {"keyword": "dentist bondi", "position": 8, "url": "https://sydneydentalcare.com.au"},
        {"keyword": "dental clinic bondi", "position": 7, "url": "https://sydneydentalcare.com.au"},
    ]

    with patch("services.claude._get_client", return_value=mock_client_instance):
        result = await generate_seo_report(
            business_name="Sydney Dental Care",
            this_week=this_week,
            last_week=last_week,
        )

    assert result == report_text
    mock_client_instance.messages.create.assert_called_once()
