class ErrorCheckNotTrue(Exception):
    def __init__(self, message="Error env. Check not in evniron"):
        self.message = message
        super().__init__(self.message)


class ErrorNotApiHashId(Exception):
    def __init__(self, message="Error env. Api_hash and api_id are not in evniron"):
        self.message = message
        super().__init__(self.message)
