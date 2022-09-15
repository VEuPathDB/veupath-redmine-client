#!env python3
# See the NOTICE file distributed with this work for additional information
# regarding copyright ownership.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from cmath import exp
from typing import List
from .issue_utils import IssueUtils
from .orgs_utils import InvalidAbbrev, OrgsUtils
from veupath.redmine.client.veupath_params import VeupathParams


class DatatypeException(Exception):
    pass


class MissingDataException(Exception):
    pass


class RedmineIssue:
    """Generic Redmine issue for Veupath."""

    def __init__(self, issue):
        self.issue = issue
        self.errors = []
        self.custom = IssueUtils.get_custom_fields(self.issue)
        self.component = self._get_component()
        self.organism_abbrev = self._get_organism_abbrev()
        self.experimental_organism = self._get_experimental_organism()
        self.operations = self._get_operations()
        self.datatype = self._get_datatype()
    
    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def _get_component(self) -> str:
        components = []
        try:
            components = self.custom["Component DB"]
        except KeyError:
            pass

        component = ''
        if len(components) == 1:
            component = components[0]
        elif len(components) == 0:
            self.add_error("No component")
        elif len(components) > 1:
            self.add_error("Several components")
        return component
    
    def _get_organism_abbrev(self) -> str:
        abbrev = ''
        try:
            abbrev = self.custom["Organism Abbreviation"]
        except KeyError:
            pass

        if abbrev:
            # Check before loading
            abbrev = abbrev.strip()
            try:
                OrgsUtils.validate_abbrev(abbrev)
            except InvalidAbbrev:
                self.add_error(f"Invalid organism_abbrev: {abbrev}")
        else:
            self.add_error("Missing organism_abbrev")
        return abbrev

    def _get_experimental_organism(self) -> str:
        experimental_organism = ''
        try:
            experimental_organism = self.custom["Experimental Organisms"]
        except KeyError:
            pass
        return experimental_organism
    
    def _get_datatype(self) -> str:
        try:
            return self.custom["DataType"]
        except KeyError:
            return ''
    
    def redmine_link(self) -> str:
        link = f"{VeupathParams.redmine_url}/issues/{self.issue.id}"
        return f'<a href="{link}">{self.issue.id}</a>'

    def _get_operations(self) -> List[str]:
        try:
            return self.custom["EBI operations"]
        except KeyError:
            return []