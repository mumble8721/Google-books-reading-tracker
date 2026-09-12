"""Entrypoint: starts the polling loop on a background thread and serves
the dashboard web app on the main thread.

Run as: python -m tracker.main
"""
import logging
import threading

from tracker.config import load_config
from tracker.poller import run_forever
from tracker.webapp import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    config = load_config()
    config.data_dir.mkdir(parents=True, exist_ok=True)

    poller_thread = threading.Thread(
        target=run_forever,
        kwargs={
            "token_path": config.token_path,
            "state_path": config.state_path,
            "log_path": config.log_path,
            "poll_interval_seconds": config.poll_interval_seconds,
        },
        name="poller",
        daemon=True,
    )
    poller_thread.start()

    app = create_app(config.log_path)
    logger.info("dashboard listening on http://0.0.0.0:%s", config.web_port)
    app.run(host="0.0.0.0", port=config.web_port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
