import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from pipeline.run_pipeline import run, main

@patch('pipeline.run_pipeline.SENATE_JSON_PATH')
@patch('pipeline.run_pipeline.HOUSE_JSON_PATH')
def test_fallback_to_official(mock_house_path, mock_senate_path):
    mock_senate_path.exists.return_value = False
    mock_house_path.exists.return_value = False
    
    from pipeline.run_pipeline import run as real_run
    
    with patch('pipeline.run_pipeline.run') as recursive_mock:
        real_run(fresh=False, senate_only=False, house_only=False, use_official=False)
        recursive_mock.assert_called_once_with(
            fresh=False, senate_only=False, house_only=False, use_official=True
        )

@patch('pipeline.scrapers.SenateOfficialScraper')
@patch('pipeline.scrapers.HouseOfficialScraper')
@patch('pipeline.run_pipeline.merge_to_csv')
def test_run_official(mock_merge, mock_house, mock_senate):
    df_senate = pd.DataFrame([{
        "chamber": "Senate", "legislator_name": "S", "ticker": "AAPL", "asset_description": "Apple",
        "asset_type": "Stock", "transaction_type": "Purchase", "transaction_date": "2023-01-01",
        "disclosure_date": "2023-01-05", "amount_range": "$1-$15k", "ptr_link": "link", "comment": "", "owner": ""
    }])
    df_house = pd.DataFrame([{
        "chamber": "House", "legislator_name": "H", "ticker": "MSFT", "asset_description": "Microsoft",
        "asset_type": "Stock", "transaction_type": "Sale", "transaction_date": "2023-01-01",
        "disclosure_date": "2023-01-05", "amount_range": "$1-$15k", "ptr_link": "link", "comment": "", "owner": ""
    }])
    
    mock_senate_instance = MagicMock()
    mock_senate_instance.scrape.return_value = df_senate
    mock_senate.return_value.__enter__.return_value = mock_senate_instance
    
    mock_house_instance = MagicMock()
    mock_house_instance.scrape.return_value = df_house
    mock_house.return_value.__enter__.return_value = mock_house_instance
    
    mock_merge.return_value = pd.DataFrame([{"chamber": "Senate"}, {"chamber": "House"}])
    
    # run with official
    run(fresh=True, senate_only=False, house_only=False, use_official=True)
    
    mock_senate_instance.scrape.assert_called_once()
    mock_house_instance.scrape.assert_called_once()
    mock_merge.assert_called_once()

@patch('pipeline.scrapers.SenateOfficialScraper')
def test_run_official_senate_only(mock_senate):
    df_senate = pd.DataFrame([{
        "chamber": "Senate", "legislator_name": "S", "ticker": "AAPL", "asset_description": "Apple",
        "asset_type": "Stock", "transaction_type": "Purchase", "transaction_date": "2023-01-01",
        "disclosure_date": "2023-01-05", "amount_range": "$1-$15k", "ptr_link": "link", "comment": "", "owner": ""
    }])
    
    mock_senate_instance = MagicMock()
    mock_senate_instance.scrape.return_value = df_senate
    mock_senate.return_value.__enter__.return_value = mock_senate_instance
    
    run(fresh=True, senate_only=True, house_only=False, use_official=True)
    mock_senate_instance.scrape.assert_called_once()

@patch('pipeline.scrapers.HouseOfficialScraper')
def test_run_official_house_only(mock_house):
    df_house = pd.DataFrame([{
        "chamber": "House", "legislator_name": "H", "ticker": "MSFT", "asset_description": "Microsoft",
        "asset_type": "Stock", "transaction_type": "Sale", "transaction_date": "2023-01-01",
        "disclosure_date": "2023-01-05", "amount_range": "$1-$15k", "ptr_link": "link", "comment": "", "owner": ""
    }])
    
    mock_house_instance = MagicMock()
    mock_house_instance.scrape.return_value = df_house
    mock_house.return_value.__enter__.return_value = mock_house_instance
    
    run(fresh=True, senate_only=False, house_only=True, use_official=True)
    mock_house_instance.scrape.assert_called_once()

@patch('pipeline.run_pipeline.get_senate_df')
def test_run_unofficial_senate_only(mock_get_senate):
    mock_get_senate.return_value = pd.DataFrame([{"chamber": "Senate"}])
    
    # This should hit the unofficial block
    with patch('pipeline.run_pipeline.SENATE_JSON_PATH') as mock_senate_path:
        mock_senate_path.exists.return_value = True
        run(fresh=False, senate_only=True, house_only=False, use_official=False)
    
    mock_get_senate.assert_called_once_with(from_cache=True)

@patch('pipeline.run_pipeline.get_house_df')
def test_run_unofficial_house_only(mock_get_house):
    mock_get_house.return_value = pd.DataFrame([{"chamber": "House"}])
    
    with patch('pipeline.run_pipeline.HOUSE_JSON_PATH') as mock_house_path:
        mock_house_path.exists.return_value = True
        run(fresh=False, senate_only=False, house_only=True, use_official=False)
    
    mock_get_house.assert_called_once_with(from_cache=True)

@patch('pipeline.run_pipeline.merge_to_csv')
def test_run_unofficial_merge(mock_merge):
    mock_merge.return_value = pd.DataFrame([{"chamber": "House"}, {"chamber": "Senate"}])
    
    with patch('pipeline.run_pipeline.SENATE_JSON_PATH') as mock_senate_path:
        with patch('pipeline.run_pipeline.HOUSE_JSON_PATH') as mock_house_path:
            mock_senate_path.exists.return_value = True
            mock_house_path.exists.return_value = True
            run(fresh=False, senate_only=False, house_only=False, use_official=False)
    
    mock_merge.assert_called_once_with(use_cache=True)

@patch('argparse.ArgumentParser.parse_args')
@patch('pipeline.run_pipeline.run')
def test_main(mock_run, mock_args):
    mock_args.return_value = MagicMock(fresh=True, senate_only=True, house_only=False, use_official=False)
    main()
    mock_run.assert_called_once_with(fresh=True, senate_only=True, house_only=False, use_official=False)
