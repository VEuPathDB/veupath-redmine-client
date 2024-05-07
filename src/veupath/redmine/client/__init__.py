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
"""Retrieve metadata from Redmine."""

import argparse

from redminelib import Redmine

from veupath.redmine.client.redmine_issue import RedmineIssue
from .veupath_params import VeupathParams
from .issue_utils import IssueUtils


__version__ = "0.1.0"


class RedmineFilter:
    """Simple object to store a list of filters to use for Redmine filtering"""

    # This is to map simple key names to actual Redmine field names
    field_map: dict = {}

    def __init__(self) -> None:
        self.fields: dict = {}

    def _map_key(self, name: str) -> str:
        """Helper to map the given filter name to the one from the field map."""
        key: str
        if name in self.field_map:
            key = self.field_map[name]
        else:
            key = name
        return key

    def set_field(self, field_name, field_value):
        """Set a field value."""
        key = self._map_key(field_name)
        self.fields[key] = field_value

    def unset_field(self, field_name):
        """Delete a field value."""
        key = self._map_key(field_name)
        del self.fields[key]


class VeupathRedmineFilter(RedmineFilter):
    """Define Veupath specific fields to filter"""

    def __init__(self) -> None:
        super().__init__()

        supported_fields = VeupathParams.issues_fields
        self.field_map = {**self.field_map, **supported_fields}


class RedmineClient:
    """Wrapper around Redmine python to set up basic interactions"""

    def __init__(self, url: str, key: str, project_id: int) -> None:
        self.redmine = Redmine(url, key=key)
        self.filter = RedmineFilter()
        self.project_id = project_id

    def get_custom_fields(self):
        """Gets the list of custom fields from the Redmine instance."""
        rs_fields = self.redmine.custom_field.all()
        yield from rs_fields

    def add_filter(self, field_name, field_value) -> None:
        """Adds a filter (key and value) for the search."""
        self.filter.set_field(field_name, field_value)

    def add_filters(self, fields: dict) -> None:
        """Adds a dictionary of filters (keys and values) for the search."""
        for field_name, field_value in fields:
            self.add_filter(field_name, field_value)

    def remove_filter(self, field_name) -> None:
        """Removes a filter for the search."""
        self.filter.unset_field(field_name)

    def get_issues(self):
        """Returns a list of issues from Redmine using the defined filter."""
        search_fields = self.filter.fields
        return list(self.redmine.issue.filter(**search_fields))

    def get_issue(self, issue_id: int):
        """Gets one issue from Redmine."""
        issue = self.redmine.issue.get(issue_id)
        return issue

    def update_custom_value(self, issue: RedmineIssue, field_name: str, field_value: str) -> bool:
        """Update one custom field value in the Redmine issue provided."""
        custom = IssueUtils.get_custom_ids(issue.issue)

        if field_name in custom:
            field_id = custom[field_name]
            feedback = self.redmine.issue.update(
                issue.issue.id, custom_fields=[{"id": field_id, "value": field_value}]
            )
            if not feedback:
                print(f"Failed to update {field_name} with value {field_value} in {issue.issue.id}")
                return False
            return True
        raise ValueError(f"Can't find custom field named {field_name}")


class VeupathRedmineClient(RedmineClient):
    """More specific Redmine client for VEuPathDB project"""

    def __init__(self, key: str) -> None:
        url = VeupathParams.redmine_url
        project_id = VeupathParams.project_id
        super().__init__(url, key, project_id)
        self.filter = VeupathRedmineFilter()

    def set_build(self, build: int) -> None:
        """Adds a build as filter for the search."""
        redmine = self.redmine
        versions = redmine.version.filter(project_id=self.project_id)
        version_name = "Build " + str(build)
        version_id = [version.id for version in versions if version.name == version_name]
        self.add_filter("build", version_id)

    def set_organism(self, organism: int) -> None:
        """Adds an organism abbreviation as filter for the search."""
        self.add_filter("organism_abbrev", organism)

    def set_component(self, component: int) -> None:
        """Adds a component DB as filter for the search."""
        self.add_filter("component", component)


def main():
    """Main entrypoint."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--key", type=str, required=True, help="Redmine authentification key")
    # Optional
    parser.add_argument("--build", type=int, help="Restrict to a given build")
    parser.add_argument(
        "--list", action="store_true", dest="list", help="Print a detailed list of all the issues"
    )
    args = parser.parse_args()

    # Start Redmine API
    redmine = VeupathRedmineClient(key=args.key)
    if args.build:
        redmine.set_build(args.build)

    redmine.add_filter("team", "Data Processing (EBI)")
    all_issues = redmine.get_issues()
    print(f"{len(all_issues)} issues selected")
    if args.list:
        IssueUtils.print_issues(all_issues, "All issues")


if __name__ == "__main__":
    main()
