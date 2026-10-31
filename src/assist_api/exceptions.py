class MissingKeyException(Exception):

    def __init__(self, key: str):
        self.key = key
        super().__init__(f'Missing {self.key} key.')

class InstitutionNotFound(Exception):

    def __init__(self, name):
        self.name = name
        super().__init__(f'Institution with name "{self.name}" not found.')

class AcademicYearNotFound(Exception):

    def __init__(self, fall_year):
        self.fall_year = fall_year
        super().__init__(f'Academic year with fall year "{self.fall_year}" not found.')

class MajorNotFound(Exception):

    def __init__(self, name):
        self.name = name
        super().__init__(f'Major with name "{self.name}" not found.')
        