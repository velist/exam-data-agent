import importlib


def test_app_package_importable():
    module = importlib.import_module("app.main")
    assert hasattr(module, "create_app")
