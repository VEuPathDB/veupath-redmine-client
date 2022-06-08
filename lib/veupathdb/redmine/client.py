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


from redminelib import Redmine, exceptions
import argparse


class IssueUtils:

    @staticmethod
    def get_custom_fields(issue) -> dict:
        """
        Put all Redmine custom fields in a dict instead of an array
        Return a dict
        """
        
        cfs = {}
        try:
            for c in issue.custom_fields:
                cfs[c["name"]] = c["value"]
        except exceptions.ResourceAttrError:
            print(f"can't get custom fields for {issue.id}")
        return cfs
    
    @staticmethod
    def tostr(issue) -> str:
        max_title = 60
        title = issue.subject
        if len(title) > max_title:
            title = title[0:max_title] + "..."
        return f"{issue.id} ({title})"


class RedmineFilter:

    field_map = {
        "status": "status_name",
        "build": "fixed_version_id",
        # Custom fields
        "team": "cf_17",
        "datatype": "cf_94",
    }

    def __init__(self) -> None:
        self.fields: dict = {}
    
    def _map_key(self, name: str) -> str:
        key: str
        if name in self.field_map:
            key = self.field_map[name]
        else:
            key = name
        return key

    def set_field(self, field_name, field_value):
        key = self._map_key(field_name)
        self.fields[key] = field_value

    def unset_field(self, field_name):
        key = self._map_key(field_name)
        del self.fields[key]


class RedmineClient:
    default_project_id = 1976

    def __init__(self, url: str, key: str) -> None:
        self.redmine = Redmine(url, key=key)
        self.filter = RedmineFilter()
        self.project_id = self.default_project_id
    
    def get_custom_fields(self):
        rs_fields = self.redmine.custom_field.all()
        for rs_field in rs_fields:
            yield rs_field

    def add_filter(self, field_name, field_value) -> None:
        self.filter.set_field(field_name, field_value)

    def add_filters(self, fields: dict) -> None:
        for field_name, field_value in fields:
            self.add_filter(field_name, field_value)

    def set_build(self, build: int) -> None:
        redmine = self.redmine
        versions = redmine.version.filter(project_id=self.project_id)
        version_name = "Build " + str(build)
        version_id = [version.id for version in versions if version.name == version_name]
        self.add_filter("build", version_id)

    def get_issues(self):
        """
        Get EBI issues from Redmine using the defined filter
        Return a list of issues
        """

        search_fields = self.filter.fields
        return list(self.redmine.issue.filter(**search_fields))
    

class VeupathRedmineClient(RedmineClient):
    url = 'https://redmine.apidb.org'
    insdc_pattern = r'^GC[AF]_\d{9}(\.\d+)?$'
    accession_api_url = "https://www.ebi.ac.uk/ena/browser/api/xml/%s"
    veupathdb_id = 1976

    def __init__(self, key: str) -> None:
        url = self.url
        super().__init__(url, key)
        self.project_id = self.veupathdb_id

    def get_all_genomes(self):
        """
        Query Redmine to get all genomes, with or without genes
        """
        datatypes = (
            "Genome sequence and Annotation",
            "Assembled genome sequence without annotation",
        )
        all_issues = []
        for datatype in datatypes:
            issues = self.get_issues({"datatype": datatype})
            print(f"{len(issues)} issues for {datatype} found")
            all_issues = all_issues + issues
        
        print(f"{len(all_issues)} issues found")
        return all_issues

    
def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Retrieve metadata from Redmine')
    
    parser.add_argument('--key', type=str, required=True,
                        help='Redmine authentification key')
    parser.add_argument('--output_dir', type=str,
                        help='Output_dir')
    # Choice
    parser.add_argument('--get',
                        choices=[
                            'genomes',
                            'rnaseq',
                            'missed_status',
                            'missed_team',
                            'missed_assignee'
                        ],
                        required=True,
                        help='Get genomes datasets, rnaseq datasets, or other missed datasets)')
    # Optional
    parser.add_argument('--build', type=int,
                        help='Restrict to a given build')
    parser.add_argument('--user_id', type=str,
                        help='Restrict to a given user')
    parser.add_argument('--current_abbrevs', type=str,
                        help='File that contains the list of current organism_abbrevs')
    args = parser.parse_args()
    
    # Start Redmine API
    redmine = VeupathRedmineClient(key=args.key)
    if args.build:
        redmine.set_build(args.build)
    
    if args.get == 'genomes':
        redmine.add_filter("team", "Data Processing (EBI)")

        redmine.add_filter("datatype", "Genome sequence and Annotation")
        full_genomes = redmine.get_issues()

        redmine.add_filter("datatype", "Assembled genome sequence without annotation")
        assembly_genomes = redmine.get_issues()

        print(f"{len(full_genomes)} genomes with annotation issues found")
        print(f"{len(assembly_genomes)} genomes without annotation issues found")

    if args.get == 'rnaseq':
        redmine.add_filter("team", "Data Processing (EBI)")
        redmine.add_filter("datatype", "RNA-seq")
        rnaseqs = redmine.get_issues()
        print(f"{len(rnaseqs)} RNA-Seq datasets issues found")

    if args.get == 'missed_datasets':
        exclude_datasets = (
            "Genome sequence and Annotation",
            "Assembled genome sequence without annotation",
            "RNA-seq"
        )

        redmine.add_filter("team", "Data Processing (EBI)")
        all_issues = redmine.get_issues()

        for issue in all_issues:
            cfs = IssueUtils.get_custom_fields(issue)
            if "DataType" in cfs:
                datatype = cfs["DataType"]
                if datatype not in exclude_datasets:
                    print(f"Unsupported datatype: {datatype} in {IssueUtils.tostr(issue)}")

    if args.get == 'missed_status':
        """Status is set to EBI, but not the team"""
        redmine.add_filter("status_id", 20)
        all_issues = redmine.get_issues()

        for issue in all_issues:
            cfs = IssueUtils.get_custom_fields(issue)
            if "VEuPathDB Team" in cfs:
                team = cfs["VEuPathDB Team"]
                if team != "Data Processing (EBI)":
                    print(f"For EBI team? {IssueUtils.tostr(issue)}")

    if args.get == 'missed_assignee':
        """Status is set to a given assignee, but not the team"""
        if not args.user_id:
            print("User id required")
            return
        redmine.add_filter("assigned_to_id", args.user_id)
        all_issues = redmine.get_issues()

        for issue in all_issues:
            cfs = IssueUtils.get_custom_fields(issue)
            if not cfs:
                print(f"Non standard issue: {issue.id} ({issue.subject})")
            if "VEuPathDB Team" in cfs:
                team = cfs["VEuPathDB Team"]
                if team != "Data Processing (EBI)":
                    print(f"For EBI team? {issue.id} ({issue.subject})")


if __name__ == "__main__":
    main()
