class AssistAPIError(Exception):
    """ base class for every error raised by assist_api """

class AcademicYearNotFound(AssistAPIError):
    """ no academic year matches the given fall year """

    def __init__(self, fall_year: int) -> None:
        self.fall_year = fall_year
        super().__init__(f'Academic year with fall year {self.fall_year} not found.')

class InstitutionNotFound(AssistAPIError):
    """ no institution matches the given name """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f'Institution "{self.name}" not found.')

class MajorNotFound(AssistAPIError):
    """ no major matches the given name """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f'Major "{self.name}" not found.')

class MissingKeyException(AssistAPIError):
    """ assist.org returned JSON that is missing a required key """

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f'Missing "{self.key}" key.')

class UnsupportedResponseError(AssistAPIError):
    """ assist.org returned a structure that isn't supported yet """