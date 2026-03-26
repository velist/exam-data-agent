from dataclasses import dataclass


@dataclass
class Application:
    name: str = "dingtalk-data-query-bot"


def create_app() -> Application:
    return Application()
