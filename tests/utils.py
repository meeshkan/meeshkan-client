class MockResponse:
    def __init__(self, json_data=None, status_code=None):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

    @property
    def text(self):
        return "Mock response"

    @property
    def ok(self):
        return self.status_code == 200

    def raise_for_status(self):
        raise RuntimeError("Raised for status {status}".format(status=self.status_code))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @staticmethod
    def for_unauthenticated():
        return MockResponse({"errors": [{"extensions": {"code": "UNAUTHENTICATED"}}]}, 200)
