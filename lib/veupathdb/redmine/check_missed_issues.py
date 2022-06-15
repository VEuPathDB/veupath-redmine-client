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


import argparse
from .client import VeupathRedmineClient
from .issue_utils import IssueUtils

supported_datatypes = (
    "Genome sequence and Annotation",
    "Assembled genome sequence without annotation",
    "RNA-seq"
)
supported_team = "Data Processing (EBI)"
supported_status_id = 20


def get_missed_datasets(redmine: VeupathRedmineClient) -> list:
    """Get issues assigned to the team, but not for a supported dataset"""

    redmine.add_filter("team", supported_team)
    all_issues = redmine.get_issues()

    missed = []
    for issue in all_issues:
        cfs = IssueUtils.get_custom_fields(issue)
        if "DataType" in cfs:
            datatype = cfs["DataType"]
            if datatype not in supported_datatypes:
                missed.append(issue)
    
    redmine.remove_filter("team")
    return missed


def get_missed_status(redmine: VeupathRedmineClient) -> list:
    """Get issues with the right status, but not the right team"""

    redmine.add_filter("status_id", supported_status_id)
    all_issues = redmine.get_issues()

    missed = []
    for issue in all_issues:
        cfs = IssueUtils.get_custom_fields(issue)
        if "VEuPathDB Team" in cfs:
            team = cfs["VEuPathDB Team"]
            if team != "Data Processing (EBI)":
                missed.append(issue)
    
    redmine.remove_filter("status_id")
    return missed


def get_missed_assignee(redmine, user_id) -> list:
    """Get issues with the right user, but not assigned to the team"""

    redmine.add_filter("assigned_to_id", user_id)
    all_issues = redmine.get_issues()

    missed = []
    for issue in all_issues:
        cfs = IssueUtils.get_custom_fields(issue)
        if not cfs:
            missed.append(issue)
        elif "VEuPathDB Team" in cfs:
            team = cfs["VEuPathDB Team"]
            if team != "Data Processing (EBI)":
                missed.append(issue)

    redmine.remove_filter("assigned_to_id")
    return missed


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='List missed issues from Redmine')
    
    parser.add_argument('--key', type=str, required=True,
                        help='Redmine authentification key')
    # Choice
    parser.add_argument('--get_missed',
                        choices=[
                            'datasets',
                            'status',
                            'assignee',
                            'all'
                        ],
                        required=True,
                        help='Check which category of issues were missed')
    # Optional
    parser.add_argument('--build', type=int,
                        help='Restrict to a given build')
    parser.add_argument('--user_id', type=str,
                        help='Restrict to a given user id (integer, or use "me" for yourself)')
    args = parser.parse_args()
    
    # Start Redmine API
    redmine = VeupathRedmineClient(key=args.key)
    if args.build:
        redmine.set_build(args.build)

    if args.get_missed == 'datasets':
        issues = get_missed_datasets(redmine)
        IssueUtils.print_issues(issues, "missed datasets")

    elif args.get_missed == 'status':
        issues = get_missed_status(redmine)
        IssueUtils.print_issues(issues, "missed status")

    elif args.get_missed == 'assignee':
        if not args.user_id:
            print("User id required for missed assignee")
            return
        issues = get_missed_assignee(redmine, args.user_id)
        IssueUtils.print_issues(issues, "missed assignee")

    elif args.get_missed == 'all':
        issues_ds = get_missed_datasets(redmine)
        IssueUtils.print_issues(issues_ds, "missed datasets")

        issues_st = get_missed_status(redmine)
        IssueUtils.print_issues(issues_st, "missed status")

        if not args.user_id:
            print("User id required for missed assignee")
            return
        issues_user = get_missed_assignee(redmine, args.user_id)
        IssueUtils.print_issues(issues_user, "missed assignee")


if __name__ == "__main__":
    main()
