from unittest.mock import MagicMock, patch

from app import initial_data


def test_initial_data_main_initializes_the_database() -> None:
    session = MagicMock()
    session.__enter__.return_value = session

    with (
        patch("app.initial_data.Session", return_value=session),
        patch("app.initial_data.init_db") as init_db,
        patch.object(initial_data.logger, "info") as log_info,
    ):
        initial_data.main()

    init_db.assert_called_once_with(session)
    assert log_info.call_count == 2
