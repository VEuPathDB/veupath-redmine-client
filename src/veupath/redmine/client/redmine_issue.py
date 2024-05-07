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
"""Generic Redmine issue object and its exceptions."""

import re
from typing import List

from .issue_utils import IssueUtils
from .orgs_utils import InvalidAbbrev, OrgsUtils
from .veupath_params import VeupathParams


class DatatypeException(Exception):
    """Raised when a datatype is wrong."""


class MissingDataException(Exception):
    """Raised when some mandatory data is missing from an issue."""


class RedmineIssue:
    """Generic Redmine issue for Veupath."""

    def __init__(self, issue):
        self.issue = issue
        self.errors = []
        self.do_log = True
        self.warnings = []
        self.custom = IssueUtils.get_custom_fields(self.issue)
        self.component = self._get_component()
        self.build = self._get_build()
        self.organism_abbrev = self._get_organism_abbrev()
        self.experimental_organism = self._get_experimental_organism()
        self.operations = set(self._get_operations())
        self.datatype = self._get_datatype()
        self.team = self._get_team()

    def add_error(self, msg: str) -> None:
        """Store one error message."""
        if self.do_log:
            self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        """Store one warning message."""
        if self.do_log:
            self.warnings.append(msg)

    def disable_log(self) -> None:
        """Disable log message storage."""
        self.do_log = False

    def enable_log(self) -> None:
        """Activate log message storage."""
        self.do_log = True

    def _get_component(self) -> str:
        """Get the VeupathDB component DB from the issue."""
        components = []
        try:
            components = self.custom["Component DB"]
        except KeyError:
            pass

        component = ""
        if len(components) == 1:
            component = components[0]
        elif len(components) == 0:
            self.add_error("No component")
        elif len(components) > 1:
            self.add_error("Several components")
        return component

    def _get_team(self) -> str:
        """Get the VeupathDB team from the issue."""
        try:
            team = self.custom["VEuPathDB Team"]
        except KeyError:
            pass

        return team

    def _get_organism_abbrev(self) -> str:
        """Get the organism abbreviation from the issue."""
        abbrev = ""
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
        """Get the experimental organism from the issue."""
        experimental_organism = ""
        try:
            experimental_organism = self.custom["Experimental Organisms"]
        except KeyError:
            pass
        return experimental_organism

    def _get_datatype(self) -> str:
        """Get the datatype from the issue."""
        try:
            return self.custom["DataType"]
        except KeyError:
            return ""

    def redmine_link(self) -> str:
        """Create an html link string to the redmine ticket."""
        link = f"{VeupathParams.redmine_url}/issues/{self.issue.id}"
        return f'<a href="{link}">{self.issue.id}</a>'

    def _get_operations(self) -> List[str]:
        """Get the list of EBI operations from the issue."""
        try:
            return self.custom["EBI operations"]
        except KeyError:
            return []

    def _get_build(self) -> str:
        """Get the VeupathDB build from the issue."""
        try:
            version = self.issue.fixed_version
            match = re.match(r"^Build (\d+)$", str(version))
            if match:
                return match.group(1)
        except KeyError:
            return ""
        return ""
