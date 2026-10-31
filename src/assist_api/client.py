from typing import Optional
from cachetools import TTLCache
from datetime import datetime, timedelta

import json
import requests

from .models import (
    AcademicYear,
    Agreement,
    Articulation,
    Course,
    Group,
    Institution,
    InstitutionAgreements,
    Major,
    Requirement,
    Section,
    Series,
    require,
)

from .exceptions import (
    AcademicYearNotFound, 
    InstitutionNotFound, 
    MajorNotFound,
)

class AssistAPI:

    def __init__(self):
        self._session = requests.Session()
        request = self._session.get('https://assist.org')
        request.raise_for_status()

        # caches
        CACHE_TTL = timedelta(days=1)

        self._get_academic_years_cache         = TTLCache(maxsize=1, ttl=CACHE_TTL, timer=datetime.now)
        self._get_institutions_cache           = TTLCache(maxsize=1, ttl=CACHE_TTL, timer=datetime.now)
        self._get_majors_cache                 = TTLCache(maxsize=100, ttl=CACHE_TTL, timer=datetime.now)
        self._get_agreement_cache              = TTLCache(maxsize=100, ttl=CACHE_TTL, timer=datetime.now)
        self._get_institution_agreements_cache = TTLCache(maxsize=100, ttl=CACHE_TTL, timer=datetime.now)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self._session.close()

    @property
    def _headers(self) -> dict[str, str]:
        return {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'X-XSRF-TOKEN': self._session.cookies['X-XSRF-TOKEN'] or '',
            'User-Agent': 'Mozilla/5.0'
        }

    def get_academic_years(self) -> tuple[AcademicYear, ...]:

        result = self._get_academic_years_cache.get(None)
        if result is not None:
            return result
        
        URL = 'https://assist.org/api/academicyears'

        request = self._session.get(URL, headers=self._headers)
        request.raise_for_status()

        data = request.json()
        academic_years = [AcademicYear.from_json(academic_year) for academic_year in data]

        # sort by id, ascending
        result = tuple(sorted(academic_years, key=lambda academic_year: academic_year.id))
        self._get_academic_years_cache[None] = result
        
        return result

    def get_institutions(self) -> tuple[Institution, ...]:

        result = self._get_institutions_cache.get(None)
        if result is not None:
            return result

        URL = 'https://assist.org/api/institutions'

        request = self._session.get(URL, headers=self._headers)
        request.raise_for_status()

        data = request.json()
        institutions = [Institution.from_json(institution) for institution in data]

        # sort by id, ascending
        result = tuple(sorted(institutions, key=lambda institution: institution.id))
        self._get_institutions_cache[None] = result

        return result

    def get_institution_agreements(self, institution: Institution | str, academic_year: AcademicYear | int) -> InstitutionAgreements:

        institution_id = institution.id if isinstance(institution, Institution) else self.query_institution(institution).id
        academic_year_id = academic_year.id if isinstance(academic_year, AcademicYear) else self.query_academic_year(academic_year).id

        key = (institution_id, academic_year_id)
        result = self._get_institution_agreements_cache.get(key)
        if result is not None:
            return result
            
        URL = f'https://assist.org/api/institutions/{institution_id}/agreements'

        request = self._session.get(URL, headers=self._headers)
        request.raise_for_status()

        data = request.json()

        # id to institution
        institution_mapping = {institution.id: institution for institution in self.get_institutions()}

        # for some reason there are 1 for 1 duplicates 
        used = set()

        sending_agreements = []
        receiving_agreements = []
        for obj in data:
            institution_parent_id, sending_year_ids, receiving_year_ids = require(obj, 'institutionParentId', 'sendingYearIds', 'receivingYearIds')

            if institution_parent_id in used:
                continue

            if any(year_id == academic_year_id for year_id in sending_year_ids):
                sending_agreements.append(institution_mapping[institution_parent_id])

            if any(year_id == academic_year_id for year_id in receiving_year_ids):
                receiving_agreements.append(institution_mapping[institution_parent_id])

            used.add(institution_parent_id)

        result = InstitutionAgreements(tuple(sending_agreements), tuple(receiving_agreements))
        self._get_institution_agreements_cache[key] = result

        return result

    def _parse_course_group(self, data) -> Course | Series:
        course_conjunction = data['courseConjunction']
        subitems = data['items']

        course_group = []

        for subitem in subitems:
            subitem_type = subitem['type']

            match subitem_type:
                case 'Course':
                    course_group.append(Course.from_json(subitem))
                case _:
                    raise NotImplementedError(f'unrecognized {subitem_type}')

        # final course group
        if len(course_group) > 1:
            return Series(
                course_conjunction,
                tuple(course_group)
            )
        elif len(course_group) == 1:
            return course_group[0]
        else:
            raise NotImplementedError('No courses')

    def _parse_course_groups(self, data) -> tuple[Course | Series, ...]:
        
        course_groups = []

        for course_group in data:
            course_group_type = course_group['type']
            
            match course_group_type:
                case 'CourseGroup':
                    course_groups.append(self._parse_course_group(course_group))
                case _:
                    raise NotImplementedError(f'unrecognized {course_group_type}')

        return tuple(course_groups)

    def _parse_sending_articulation(self, sending_articulation) -> Optional[Course | Series]:
        course_group_conjunctions = sending_articulation['courseGroupConjunctions'] or []
        course_groups = self._parse_course_groups(sending_articulation['items'])

        # final sending  articulation
        if len(course_groups) > 1:
            # make more robust and actually attach each group conjucnction to its courses
            # course group conjunctions could be just display...

            conjunctions = {course_group_conjunction['groupConjunction'] for course_group_conjunction in course_group_conjunctions}
            if len(conjunctions) > 1:
                raise NotImplementedError('More than one group conjunction, tell Andrew to implement this')

            # use first conjunction otherwise assume and when missing (courses appear stacked)
            return Series(
                course_group_conjunctions[0]['groupConjunction'] if len(course_group_conjunctions) >= 1 else 'And',
                tuple(course_groups)
            )

        elif len(course_groups) == 1:
            return course_groups[0]
        else:
            # potentially do something with ts info?
            no_articulation_reason = sending_articulation['noArticulationReason']
            return None
        
    def _parse_sending_articulations(self, articulations) -> dict[str, Course | Series]:

        sending = {}

        for articulation in articulations:
            template_cell_id = articulation['templateCellId']

            sending_articulation = articulation['articulation']['sendingArticulation']
            sending_articulation_type = sending_articulation['type']

            match sending_articulation_type:
                case 'SendingArticulation':
                    sending[template_cell_id] = self._parse_sending_articulation(sending_articulation)
                case 'TemplateOverride':
                    # WTF is this? Found in SJDC -> Davis, Computer Science & Engineering B.S., 2025
                    pass
                case _:
                    raise NotImplementedError(f'unrecognized {sending_articulation_type}')
        
        return sending

    def _parse_cell(self, cell, sending) -> Optional[Articulation]:
        cell_id = cell['id']
        cell_type = cell['type']

        match cell_type:
            case 'Course':
                receiving = Course.from_json(cell['course'])
            case 'Series':
                receiving = Series.from_json(cell['series'])
            case 'Requirement':
                receiving = Requirement.from_json(cell['requirement'])
            case 'CSUGE' | 'CALGETC' | 'GeneralEducation':
                return None
            case _:
                raise NotImplementedError(f'unrecognized {cell_type}')

        return Articulation(sending.get(cell_id), receiving)

    def _parse_row(self, row, sending) -> list[Articulation]:
        position, cells, attributes = require(row, 'position', 'cells', 'attributes')
        result = []

        for cell in cells:
            articulation = self._parse_cell(cell, sending)
            if articulation:
                result.append(articulation)

        return result

    def _parse_section(self, section, sending) -> Optional[Section]:
        section_type, = require(section, 'type')

        match section_type:
            case 'Section':
                rows, = require(section, 'rows')
                articulations = [articulation for row in rows for articulation in self._parse_row(row, sending)]
                return Section(tuple(articulations))
            case 'SectionHeader':
                return None
            case _:
                raise NotImplementedError(f'unrecognized {section_type}')

    def _parse_group(self, asset, sending) -> Optional[Group]:
        asset_type = asset['type']

        match asset_type:
            case 'RequirementGroup':
                # sections key is needed to parse sections but Group class has sections as a tuple of Section class... need to combine the two somehow
                hide_section_letters, sections, attributes, show_conjunction_between_sections, academic_year_id, institution_parent_id, institution, advisements, group_id, position, area = require(
                    asset,
                    'hideSectionLetters',
                    'sections',
                    'attributes',
                    'showConjunctionBetweenSections',
                    'academicYearId',
                    'institutionParentId',
                    'instruction',
                    'advisements',
                    'groupId',
                    'position',
                    'area'
                )

                # sections
                group_sections = []
                for section in sections:
                    parsed_section = self._parse_section(section, sending)
                    if parsed_section:
                        group_sections.append(parsed_section)

                return Group(tuple(group_sections))
            case 'GeneralText' | 'RequirementTitle' | 'GeneralTitle':
                return None  
            case _:
                raise NotImplementedError(f'unrecognized {asset_type}')
       
    def _parse_groups(self, template_assets, sending) -> list[Group]:
        groups = []
        for asset in template_assets:
            group = self._parse_group(asset, sending)
            if group:
                groups.append(group)    
        return groups
                
    def get_majors(self, sending_institution: Institution | str, receiving_institution: Institution | str, academic_year: AcademicYear | int) -> tuple[Major, ...]:

        receiving_institution_id = receiving_institution.id if isinstance(receiving_institution, Institution) else self.query_institution(receiving_institution).id
        sending_institution_id = sending_institution.id if isinstance(sending_institution, Institution) else self.query_institution(sending_institution).id
        academic_year_id = academic_year.id if isinstance(academic_year, AcademicYear) else self.query_academic_year(academic_year).id

        key = (receiving_institution_id, sending_institution_id, academic_year_id)
        
        result = self._get_majors_cache.get(key)
        if result is not None:
            return result

        URL = 'https://assist.org/api/agreements'

        params = {
            'receivingInstitutionId': receiving_institution_id,
            'sendingInstitutionId': sending_institution_id,
            'academicYearId': academic_year_id,
            'categoryCode': 'major'
        }

        request = self._session.get(
            url=URL,
            headers=self._headers,
            params=params
        )

        request.raise_for_status()

        data = request.json()
        reports, = require(data, 'reports')

        majors = [Major.from_json(major) for major in reports]
        result =  tuple(sorted(majors, key=lambda major: major.name))

        self._get_majors_cache[key] = result
        return result

    def get_agreement(self, major: Major) -> Agreement:

        key = major.key

        result = self._get_agreement_cache.get(key)
        if result is not None:
            return result

        URL = 'https://assist.org/api/articulation/Agreements'

        params = {
            'Key': f'{major.key}'
        }

        request = self._session.get(URL, params=params, headers=self._headers)
        request.raise_for_status()

        data = request.json()

        # id to Course | Series
        articulations = json.loads(data['result']['articulations'])
        sending = self._parse_sending_articulations(articulations)

        template_assets = json.loads(data['result']['templateAssets'])
        groups = self._parse_groups(template_assets, sending)

        result = Agreement(tuple(groups))
        self._get_agreement_cache[key] = result

        return result

    def query_academic_year(self, fall_year: int) -> AcademicYear:
        result = next(
            (academic_year for academic_year in self.get_academic_years() if academic_year.fall_year == fall_year),
            None
        )

        if result is None:
            raise AcademicYearNotFound(fall_year)

        return result

    def query_institution(self, name: str) -> Institution:
        result = next(
            (institution for institution in self.get_institutions() if institution.get_name() == name),
            None
        )

        if result is None:
            raise InstitutionNotFound(name)

        return result

    def query_major(self, sending_institution: Institution | str, receiving_institution: Institution | str, academic_year: AcademicYear | int, major_name: str) -> Major:
        result = next(
            (major for major in self.get_majors(sending_institution, receiving_institution, academic_year) if major.name == major_name),
            None
        )

        if result is None:
            raise MajorNotFound(major_name)

        return result
    
