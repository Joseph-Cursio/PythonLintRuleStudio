import pytest
from src.ruff_studio import cache_manager
from unittest.mock import patch, mock_open, MagicMock

@pytest.fixture(autouse=True)
def mock_cache_file():
    """Fixture to mock the cache file path and its content."""
    mock_path = MagicMock(spec=cache_manager.Path)
    mock_path.is_file.return_value = True

    with patch('src.ruff_studio.cache_manager.CACHE_FILE', mock_path):
        with patch('builtins.open', mock_open(read_data='{"test_key": {"version": "1.0", "data": "test_data"}}')) as mock_file:
            yield mock_file

def test_get_cache_existing_key():
    """Tests retrieving an existing key from the cache."""
    result = cache_manager.get_cache("test_key")
    assert result == {"version": "1.0", "data": "test_data"}

def test_get_cache_non_existing_key():
    """Tests retrieving a non-existing key from the cache."""
    result = cache_manager.get_cache("non_existing_key")
    assert result is None

def test_set_cache(mock_cache_file):
    """Tests setting a new key-value pair in the cache."""
    cache_manager.set_cache("new_key", {"version": "2.0", "data": "new_data"})

    # Check that open was called for writing
    mock_cache_file.assert_called_with(cache_manager.CACHE_FILE, 'w')

    # Check that the data was written correctly
    handle = mock_cache_file()
    import json
    expected_data = {
        "test_key": {"version": "1.0", "data": "test_data"},
        "new_key": {"version": "2.0", "data": "new_data"}
    }
    # Get all the separate strings passed to write and join them.
    written_data = "".join(call[0][0] for call in handle.write.call_args_list)
    assert json.loads(written_data) == expected_data
