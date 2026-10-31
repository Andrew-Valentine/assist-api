from dataclasses import dataclass, field
from typing import Optional, Any

from .exceptions import MissingKeyException

def require(obj: dict, *keys) -> tuple[Any, ...]:
    """ raise on missing key """

    values = []
    for key in keys:
        if key not in obj:
            raise MissingKeyException(key)
        values.append(obj[key])
    return tuple(values)

def optional(obj: dict, *keys) -> tuple[Any, ...]:
    """ allow missing key """

    return tuple(obj.get(key) for key in keys)

@dataclass(frozen=True)
class AcademicYear:

    id: int
    fall_year: int
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_json(cls, data):
        id, fall_year = require(data, 'id', 'fallYear')
        return cls(id, fall_year, data)

@dataclass(frozen=True)
class InstitutionName:

    name: str
    from_year: Optional[int]
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    
    @classmethod
    def from_json(cls, data):
        name, has_departments, hide_in_list = require(data, 'name', 'hasDepartments', 'hideInList')
        alternate_institution_id, from_year = optional(data, 'alternateInstitutionId', 'fromYear')

        return cls(
            name,
            from_year,
            data
        )

@dataclass(frozen=True)
class TermTypeAcademicYear:

    term_type: int
    from_year: int

    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    
    @classmethod
    def from_json(cls, data):
        term_type, from_year = require(data, 'termType', 'fromYear')

        return cls(
            term_type,
            from_year,
            data
        )

@dataclass(frozen=True)
class Institution:

    id: int
    names: tuple[InstitutionName, ...]
    code: str
    is_community_college: bool
    term_type: int
    begin_id: int
    end_id: Optional[int]
    term_type_academic_years: tuple[TermTypeAcademicYear, ...]

    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def get_name(self, academic_year: Optional[int | AcademicYear]=None) -> Optional[str]:
        """ get the name of the institution during a specified year """

        if isinstance(academic_year, AcademicYear):
            academic_year = academic_year.fall_year

        # remove future years if current year specified
        if academic_year is not None:
            names = [name for name in self.names if not name.from_year or name.from_year <= academic_year]
        else:
            names = self.names

        if len(names) == 1:
            return names[0].name

        # sort by year, descending and remove old names (from_year == None)
        valid_names = sorted(
            (name for name in names if name.from_year is not None), 
            key=lambda name: -name.from_year
            )

        if len(valid_names) > 0:
            return valid_names[0].name
        else:
            return None

    @classmethod
    def  from_json(cls, data):
        id, names, code, prefers_2016_legacy_report, is_community_college, category, term_type, begin_id, term_type_academic_years = require(
            data,
            'id',
            'names',
            'code',
            'prefers2016LegacyReport',
            'isCommunityCollege',
            'category',
            'termType',
            'beginId',
            'termTypeAcademicYears'
        )
        end_id, = optional(data, 'endId')

        return cls(
            id,
            tuple(InstitutionName.from_json(name) for name in names),
            code,
            is_community_college,
            term_type,
            begin_id,
            end_id,
            tuple(TermTypeAcademicYear.from_json(term_type_academic_year) for term_type_academic_year in term_type_academic_years),
            data
        )

    def get_code(self):
        """ get the code of the institution """

        return self.code.strip()

@dataclass(frozen=True)
class InstitutionAgreements:

    sending: tuple[Institution, ...]
    receiving: tuple[Institution, ...]

@dataclass(frozen=True)
class Major:

    key: str
    name: str
    institution_id: int

    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __repr__(self) -> str:
        return f'{self.name}'

    @classmethod
    def from_json(cls, data):
        key, label, owner_institution_id = require(data, 'key', 'label', 'ownerInstitutionId')
        return cls(key, label, owner_institution_id, data)

@dataclass(frozen=True)
class Course:

    title: str
    number: str
    prefix: str    
    prefix_description: str
    department: str
    begin: str
    end: str
    min_units: float
    max_units: float

    position: int

    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __repr__(self):
        return f'{self.prefix} {self.number}'

    @classmethod
    def from_json(cls, data):
        course_identifier_parent_id, course_title, course_number, prefix, prefix_parent_id, prefix_description, department_parent_id, department, begin, end, min_units, max_units, pathways = require(
            data,
            'courseIdentifierParentId',
            'courseTitle',
            'courseNumber',
            'prefix',
            'prefixParentId',
            'prefixDescription',
            'departmentParentId',
            'department', 
            'begin',
            'end',
            'minUnits',
            'maxUnits',
            'pathways',
        )

        visible_cross_listed_courses, requisites, attributes, published_course_identifier_year_term_id, position = optional(
            data, 
            'visibleCrossListedCourses', 
            'requisites', 
            'attributes', 
            'publishedCourseIdentifierYearTermId', 
            'position'
        )

        return cls(
            course_title,
            course_number,
            prefix,
            prefix_description,
            department,
            begin,
            end,
            min_units,
            max_units,
            position,
            data
        )

@dataclass(frozen=True)
class Series:

    conjunction: str
    children: tuple[Course, ...]

    def __repr__(self):
        return f'({f" {self.conjunction} ".join([child.__repr__() for child in self.children])})'

    @classmethod
    def from_json(cls, data):
        conjunction, name, courses, series_pathways = require(
            data,
            'conjunction',
            'name',
            'courses',
            'seriesPathways'
        )

        children = [Course.from_json(course) for course in courses]
        return cls(conjunction, tuple(children))

@dataclass(frozen=True)
class Requirement:

    name: str

    @classmethod
    def from_json(cls, data):
        name, = require(data, 'name')

        return cls(name)

@dataclass(frozen=True)
class Articulation:

    sending: Optional[Course | Series]
    receiving: Course | Series | Requirement

    def __repr__(self) -> str:
        return f'{self.sending} -> {self.receiving}'

@dataclass(frozen=True)
class Section:

    articulations: tuple[Articulation, ...]

@dataclass(frozen=True)
class Group:

    sections: tuple[Section, ...]

@dataclass(frozen=True)
class Agreement:

    groups: tuple[Group, ...]

    @property
    def sections(self):
        return [section for group in self.groups for section in group.sections]

    @property
    def articulations(self):
        return [articulation for section in self.sections for articulation in section.articulations]

    @property
    def articulated(self):
        return list(filter(lambda articulation: articulation.sending is not None, self.articulations))

    @property
    def not_articulated(self):
        return list(filter(lambda articulation: articulation.sending is None, self.articulations))

    @property
    def complete(self) -> bool:
        return len(self.not_articulated) == 0
                    