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
async def test_get_maps_rankings_matched_by_place_id():
    """get_maps_rankings returns map_position when the client's place_id matches."""
    from services.dataforseo import get_maps_rankings

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "tasks": [{
            "result": [{
                "items": [
                    {"type": "maps_search", "rank_absolute": 1, "title": "Other Clinic", "place_id": "PLACE_OTHER"},
                    {"type": "maps_search", "rank_absolute": 5, "title": "Sydney Dental Care", "place_id": "PLACE_OURS"},
                ]
            }]
        }]
    }

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post.return_value = mock_response

    with patch("services.dataforseo.httpx.AsyncClient", return_value=mock_client):
        result = await get_maps_rankings(
            keyword="dentist bondi",
            location="Bondi Junction",
            client_suburb="Bondi",
            business_name="Sydney Dental Care",
            place_id="PLACE_OURS",
        )

    assert result["keyword"] == "dentist bondi"
    assert result["map_position"] == 5
    assert result["place_id"] == "PLACE_OURS"
    assert result["matched"] is True


@pytest.mark.asyncio
async def test_get_maps_rankings_matched_by_business_name():
    """get_maps_rankings matches by normalized title when no place_id is provided."""
    from services.dataforseo import get_maps_rankings

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "tasks": [{
            "result": [{
                "items": [
                    {"type": "maps_search", "rank_absolute": 2, "title": "Sydney Dental Care", "place_id": "P1"},
                    {"type": "maps_search", "rank_absolute": 3, "title": "Bondi Dental", "place_id": "P2"},
                ]
            }]
        }]
    }

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post.return_value = mock_response

    with patch("services.dataforseo.httpx.AsyncClient", return_value=mock_client):
        result = await get_maps_rankings(
            keyword="dentist bondi",
            location="Bondi",
            client_suburb="Bondi",
            business_name="sydney dental care",  # different case
            place_id="",
        )

    assert result["matched"] is True
    assert result["map_position"] == 2


@pytest.mark.asyncio
async def test_get_maps_rankings_no_match():
    """get_maps_rankings returns matched=False when no item matches the business."""
    from services.dataforseo import get_maps_rankings

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "tasks": [{
            "result": [{
                "items": [
                    {"type": "maps_search", "rank_absolute": 1, "title": "Other Clinic", "place_id": "P1"},
                    {"type": "maps_search", "rank_absolute": 2, "title": "Another Clinic", "place_id": "P2"},
                ]
            }]
        }]
    }

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.post.return_value = mock_response

    with patch("services.dataforseo.httpx.AsyncClient", return_value=mock_client):
        result = await get_maps_rankings(
            keyword="dentist bondi",
            location="Bondi",
            client_suburb="Bondi",
            business_name="Sydney Dental Care",
            place_id="",
        )

    assert result["matched"] is False
    assert result["map_position"] is None


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


@pytest.mark.asyncio
async def test_seo_report_prompt_includes_organic_and_map_deltas():
    """generate_seo_report prompt payload includes both organic and map deltas."""
    from services.claude import generate_seo_report

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Report text.")]
    mock_client_instance = MagicMock()
    mock_client_instance.messages.create.return_value = mock_response

    this_week = [
        {"keyword": "dentist bondi", "position": 3, "map_position": 2},
    ]
    last_week = [
        {"keyword": "dentist bondi", "position": 8, "map_position": 5},
    ]

    with patch("services.claude._get_client", return_value=mock_client_instance):
        await generate_seo_report(
            business_name="Sydney Dental Care",
            this_week=this_week,
            last_week=last_week,
        )

    call_kwargs = mock_client_instance.messages.create.call_args.kwargs
    # The system prompt mentions "search rank" and "map rank" phrasing.
    assert "search rank" in call_kwargs["system"]
    assert "map rank" in call_kwargs["system"]
    # The user content includes both organic and map delta fields.
    user_content = call_kwargs["messages"][0]["content"]
    assert "search_delta" in user_content
    assert "map_delta" in user_content
    assert "search_this_week" in user_content
    assert "map_this_week" in user_content


@pytest.mark.asyncio
async def test_seo_report_upsert_includes_both_positions():
    """seo_report upsert payload includes both position and map_position."""
    from jobs.seo_report import run_seo_rankings_all_clients

    upsert_payloads = []

    mock_db = MagicMock()

    def _table(name):
        chain = MagicMock()
        if name == "clients":
            chain.select.return_value.contains.return_value.execute.return_value = MagicMock(
                data=[{
                    "id": "c1",
                    "business_name": "Sydney Dental Care",
                    "email": "test@test.com",
                    "suburb": "Bondi",
                    "state": "NSW",
                    "keywords": ["dentist bondi"],
                }]
            )
        elif name == "locations":
            chain.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=None
            )
        elif name == "rankings":
            # Capture upsert payload.
            def _upsert(payload, **kwargs):
                upsert_payloads.append(payload)
                return chain
            chain.upsert.side_effect = _upsert
            chain.upsert.return_value.execute.return_value = MagicMock(data=[])
            # _fetch_rankings (this week + last week) returns empty.
            chain.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        return chain

    mock_db.table.side_effect = _table

    organic_result = {"keyword": "dentist bondi", "position": 3, "url": "https://sdc.com.au"}
    maps_result = {"keyword": "dentist bondi", "map_position": 5, "place_id": "P1", "matched": True}

    with patch("jobs.seo_report.get_db", return_value=mock_db), \
         patch("jobs.seo_report._fetch_rankings_from_api", new_callable=AsyncMock, return_value=organic_result), \
         patch("jobs.seo_report._fetch_maps_rankings_from_api", new_callable=AsyncMock, return_value=maps_result), \
         patch("jobs.seo_report._generate_report_safe", new_callable=AsyncMock, return_value="Report"), \
         patch("jobs.seo_report.send_seo_email", new_callable=AsyncMock):
        await run_seo_rankings_all_clients()

    assert len(upsert_payloads) == 1
    payload = upsert_payloads[0]
    assert payload["position"] == 3
    assert payload["map_position"] == 5
    assert payload["keyword"] == "dentist bondi"
