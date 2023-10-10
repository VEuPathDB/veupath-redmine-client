#!/usr/bin/env python
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

from Bio import Entrez

from veupath.redmine.client import VeupathRedmineClient
from veupath.redmine.client.genome import Genome
from veupath.redmine.client.rnaseq import RNAseq
from veupath.redmine.client.redmine_issue import RedmineIssue


supported_team = "Data Processing (EBI)"


def check_genome_issue(redmine: VeupathRedmineClient, issue_id: int, build: int) -> list:
    """Check a single issue given an ID"""

    issue = redmine.get_issue(issue_id)
    redmine_issue = RedmineIssue(issue)
    datatype = redmine_issue.custom["DataType"]

    # Check what kind of issue it is
    if datatype in Genome.supported_datatypes:
        print("Genome issue identified")
        redmine_issue = Genome(issue)
        redmine_issue.parse()
        check_issue(redmine_issue, build)
    elif datatype in RNAseq.supported_datatypes:
        print("RNA-Seq dataset issue identified")
        redmine_issue = RNAseq(issue)
        redmine_issue.parse()
        check_issue(redmine_issue, build)
    else:
        print(f"Unsupported datatype {datatype} for issue {issue_id}")

    errors = redmine_issue.errors
    warnings = redmine_issue.warnings
    if errors:
        print(f"This issue has {len(errors)} errors:")
        [print(f"- {error}") for error in errors]
    if warnings:
        print(f"This issue has {len(warnings)} warnings:")
        [print(f"- {warning}") for warning in warnings]
    if not (errors or warnings):
        print("No error found")


def check_issue(issue: RedmineIssue, build: str):
    if not issue.team == supported_team:
        issue.add_error(f"team is not {supported_team}")
    if not issue.build == build:
        issue.add_error(f"Wrong build: issue has {issue.build}")


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Check a single issue from Redmine")

    parser.add_argument("--key", type=str, required=True, help="Redmine authentication key")

    parser.add_argument("--id", type=str, required=True, help="ID of the issue to check")

    # Optional
    parser.add_argument("--build", type=str, help="Restrict to a given build")
    parser.add_argument("--email", type=str, help="Set this email to use Entrez and check the INSDC records")
    args = parser.parse_args()

    # Start Redmine API
    redmine = VeupathRedmineClient(key=args.key)
    if args.email:
        Entrez.email = args.email
    else:
        print("Tips: provide an email to also check if there is an annotation in INSDC")
    check_genome_issue(redmine, args.id, args.build)


if __name__ == "__main__":
    main()
