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

import re
from .issue_utils import IssueUtils
from .orgs_utils import InvalidAbbrev, OrgsUtils


class DatatypeException(Exception):
    pass


class MissingDataException(Exception):
    pass


class RedmineIssue:
    """Generic Redmine issue for Veupath."""

    def __init__(self, issue):
        self.issue = issue
        self.custom = IssueUtils.get_custom_fields(self.issue)
        self.component = ""
        self.organism_abbrev = ""
        self.experimental_organism = ""
        self.errors = []
    
    def _add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def _get_component(self) -> None:
        try:
            components = self.custom["Component DB"]
        except KeyError:
            components = []

        if len(components) == 1:
            self.component = components[0]
        elif len(components) == 0:
            self._add_error("No component")
        elif len(components) > 1:
            self._add_error("Several components")
    
    def _get_organism_abbrev(self) -> None:
        try:
            abbrev = self.custom["Organism Abbreviation"]
        except KeyError:
            abbrev = ""

        if abbrev:
            # Check before loading
            abbrev = abbrev.strip()
            try:
                OrgsUtils.validate_abbrev(abbrev)
            except InvalidAbbrev:
                self._add_error(f"Invalid organism_abbrev: {abbrev}")
            self.organism_abbrev = abbrev
        else:
            self._add_error("Missing organism_abbrev")

    def _get_experimental_organism(self) -> None:
        self.experimental_organism = self.custom["Experimental Organisms"]
    
    @staticmethod
    def _check_organism_abbrev(name) -> bool:
        """Basic check for organism_abbrev format."""
        if re.search(r'^([A-Za-z0-9_.-]+)$', name):
            return True
        else:
            return False
